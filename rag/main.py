from __future__ import annotations


from rag.retriever import ArticleRetriever
from pathlib import Path
from rag.kg_client import LocalKnowledgeGraph
from rag.pipeline import ArticleRAGPipeline


def main() -> None:
    retriever = ArticleRetriever()

    retriever.load(
        "data/processed/rag_index"
    )

    knowledge_graph = LocalKnowledgeGraph(
        ttl_path=Path(
            "data/processed/knowledge_graph.ttl"
        )
    )

    assistant = ArticleRAGPipeline(
        retriever=retriever,
        knowledge_graph=knowledge_graph,
    )

    print(
        "Ask for the abstract of an academic paper. "
        "Type 'exit' to stop."
    )

    while True:
        question = input(
            "\nQuestion: "
        ).strip()

        if question.casefold() in {
            "exit",
            "quit",
        }:
            break

        if not question:
            continue

        try:
            answer = assistant.answer_question(
                question=question
            )
        except Exception as error:
            answer = f"Error: {error}"

        print(f"\n{answer}")


if __name__ == "__main__":
    main()