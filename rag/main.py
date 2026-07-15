from rag.models import Article
from rag.pipeline import ArticleRAGPipeline
from rag.retriever import ArticleRetriever


def create_test_articles() -> list[Article]:
    return [
        Article(
            article_id="article-001",
            title="Attention Is All You Need",
            abstract=(
                "The dominant sequence transduction models "
                "are based on complex recurrent or convolutional "
                "neural networks that include an encoder and a "
                "decoder. The authors propose a new architecture "
                "based solely on attention mechanisms."
            ),
            metadata={
                "authors": [
                    "Ashish Vaswani",
                    "Noam Shazeer",
                ],
                "year": 2017,
            },
        ),
        Article(
            article_id="article-002",
            title=(
                "Retrieval-Augmented Generation for "
                "Knowledge-Intensive NLP Tasks"
            ),
            abstract=(
                "The paper introduces retrieval-augmented "
                "generation models that combine parametric "
                "and non-parametric memory for "
                "knowledge-intensive natural language "
                "processing tasks."
            ),
            metadata={
                "authors": [
                    "Patrick Lewis",
                    "Ethan Perez",
                ],
                "year": 2020,
            },
        ),
        Article(
            article_id="article-003",
            title=(
                "Graph Retrieval-Augmented Generation: "
                "A Survey"
            ),
            abstract=(
                "This article surveys retrieval-augmented "
                "generation approaches that use graph-structured "
                "knowledge to support retrieval and generation."
            ),
            metadata={
                "year": 2024,
                "keywords": [
                    "GraphRAG",
                    "knowledge graphs",
                    "retrieval",
                ],
            },
        ),
    ]


def main() -> None:
    articles = create_test_articles()

    retriever = ArticleRetriever()

    retriever.build_index(articles)

    rag = ArticleRAGPipeline(
        retriever=retriever
    )

    requested_title = (
        "Retrieval-Augmented Generation for "
        "Knowledge-Intensive NLP Tasks"
    )

    answer = rag.generate_abstract(
        requested_title=requested_title
    )

    print(answer)


if __name__ == "__main__":
    main()