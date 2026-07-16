from __future__ import annotations

import json
import re
import faiss
import numpy as np
from dataclasses import asdict
from pathlib import Path
from sentence_transformers import SentenceTransformer

from rag.models import Article, RetrievedArticle


class ArticleRetriever:
    def __init__(self, embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2", ) -> None:
        self.embedding_model_name = embedding_model_name
        self.embedding_model = SentenceTransformer(embedding_model_name)
        self.articles: list[Article] = []
        self.index: faiss.IndexFlatIP | None = None

    @staticmethod
    def normalize_title(title: str) -> str:
        title = title.casefold()
        title = re.sub(r"[^\w\s]", " ", title)
        title = re.sub(r"\s+", " ", title)

        return title.strip()

    def _encode_articles(self, texts: list[str], ) -> np.ndarray:
        if hasattr(self.embedding_model, "encode_document", ):
            embeddings = self.embedding_model.encode_document(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=True,
            )
        else:
            embeddings = self.embedding_model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=True,
            )

        return np.asarray(embeddings, dtype=np.float32, )

    def _encode_query(self, query: str, ) -> np.ndarray:
        if hasattr(self.embedding_model, "encode_query", ):
            embedding = self.embedding_model.encode_query(
                query,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        else:
            embedding = self.embedding_model.encode(
                query,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )

        embedding = np.asarray(embedding, dtype=np.float32, )

        if embedding.ndim == 1:
            embedding = embedding.reshape(1, -1)

        return embedding

    def build_index(self, articles: list[Article], ) -> None:
        valid_articles = [
            article
            for article in articles
            if article.title.strip()
               and article.abstract.strip()
        ]

        if not valid_articles:
            raise ValueError("No valid articles were provided.")

        self.articles = valid_articles
        texts = [article.text_for_embedding() for article in self.articles]
        embeddings = self._encode_articles(texts)
        embedding_dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(embedding_dimension)
        self.index.add(embeddings)
        print(f"Indexed {len(self.articles)} articles.")

    def _find_exact_matches(self, requested_title: str, ) -> list[RetrievedArticle]:
        normalized_requested_title = self.normalize_title(requested_title)

        matches = []

        for article in self.articles:
            normalized_article_title = self.normalize_title(article.title)

            if normalized_article_title == normalized_requested_title:
                matches.append(
                    RetrievedArticle(
                        article=article,
                        similarity_score=1.0,
                        match_type="exact_title",
                    )
                )

        return matches

    def retrieve(self, requested_title: str, top_k: int = 3, ) -> list[RetrievedArticle]:
        if self.index is None:
            raise RuntimeError("The index has not been built or loaded.")

        requested_title = requested_title.strip()

        if not requested_title:
            raise ValueError("The requested title cannot be empty.")

        exact_matches = self._find_exact_matches(requested_title)

        if exact_matches:
            return exact_matches[:top_k]

        normalized_requested_title = self.normalize_title(requested_title)

        query = (f"Find the academic article with this title: {requested_title}")

        query_embedding = self._encode_query(query)
        candidate_count = min(max(top_k * 5, 10), len(self.articles))
        scores, indices = self.index.search(query_embedding, candidate_count)
        results: list[RetrievedArticle] = []

        for score, article_index in zip(scores[0], indices[0]):
            if article_index < 0:
                continue

            article = self.articles[int(article_index)]
            normalized_candidate_title = self.normalize_title(article.title)

            final_score = float(score)
            match_type = "semantic"

            if (
                    normalized_requested_title
                    in normalized_candidate_title
                    or normalized_candidate_title
                    in normalized_requested_title
            ):
                final_score += 0.20
                match_type = "partial_title"

            results.append(
                RetrievedArticle(
                    article=article,
                    similarity_score=final_score,
                    match_type=match_type,
                )
            )

        results.sort(
            key=lambda result: result.similarity_score,
            reverse=True,
        )

        return results[:top_k]

    def save(self, output_directory: str | Path) -> None:
        if self.index is None:
            raise RuntimeError("Build the index before saving it.")

        output_directory = Path(output_directory)
        output_directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(output_directory / "articles.faiss"))

        article_data = [asdict(article) for article in self.articles]

        with (output_directory / "articles.json").open("w", encoding="utf-8") as file:
            json.dump(article_data, file, ensure_ascii=False, indent=2)

        configuration = {"embedding_model_name": self.embedding_model_name}

        with (output_directory / "retriever_config.json").open("w", encoding="utf-8",) as file:
            json.dump(configuration, file, indent=2)

    def load(self, input_directory: str | Path) -> None:
        input_directory = Path(input_directory)
        index_path = (input_directory / "articles.faiss")

        articles_path = (input_directory / "articles.json")

        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index not found: {index_path}")

        if not articles_path.exists():
            raise FileNotFoundError(f"Article file not found: {articles_path}")

        self.index = faiss.read_index(str(index_path))

        with articles_path.open("r", encoding="utf-8") as file:
            raw_articles = json.load(file)

        self.articles = [Article(**article) for article in raw_articles]