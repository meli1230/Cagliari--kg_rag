from __future__ import annotations

import csv
from pathlib import Path

from rag.models import Article
from rag.retriever import ArticleRetriever


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CSV_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "knowledge_graph.csv"
)

INDEX_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "rag_index"
)


def load_articles(csv_path: Path) -> list[Article]:
    articles: list[Article] = []

    with csv_path.open("r", encoding="utf-8", newline="",) as file:
        reader = csv.DictReader(file)

        for row in reader:
            article_id = (
                row.get("article_id")
                or row.get("id")
                or row.get("arxiv_id")
                or ""
            ).strip()

            title = (
                row.get("title")
                or ""
            ).strip()

            abstract = (
                row.get("abstract")
                or ""
            ).strip()

            if not title or not abstract:
                continue

            excluded_columns = {
                "article_id",
                "id",
                "arxiv_id",
                "title",
                "abstract",
            }

            metadata = {
                key: value
                for key, value in row.items()
                if key not in excluded_columns
                and value not in {
                    None,
                    "",
                }
            }

            articles.append(
                Article(
                    article_id=article_id,
                    title=title,
                    abstract=abstract,
                    metadata=metadata,
                )
            )

    return articles


def main() -> None:
    articles = load_articles(CSV_PATH)

    if not articles:
        raise RuntimeError(
            f"No valid articles were found in {CSV_PATH}"
        )

    print(f"Loaded {len(articles)} articles.")
    retriever = ArticleRetriever()
    retriever.build_index(articles)
    retriever.save(INDEX_DIRECTORY)
    print(f"Saved FAISS index to: {INDEX_DIRECTORY}")


if __name__ == "__main__":
    main()