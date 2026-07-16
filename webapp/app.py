from pathlib import Path
from flask import Flask, render_template, request, jsonify

from rag.retriever import ArticleRetriever
from rag.kg_client import LocalKnowledgeGraph
from rag.pipeline import ArticleRAGPipeline

app = Flask(__name__)

retriever = ArticleRetriever()
retriever.load("data/processed/rag_index")

knowledge_graph = LocalKnowledgeGraph(
    ttl_path=Path("data/processed/knowledge_graph.ttl")
)

assistant = ArticleRAGPipeline(
    retriever=retriever,
    knowledge_graph=knowledge_graph,
)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()

    if not question:
        return jsonify({"answer": "No question provided."}), 400

    try:
        answer = assistant.answer_question(question=question)
    except Exception as error:
        return jsonify({"answer": f"Error: {error}"}), 500

    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(debug=True, port=5000)