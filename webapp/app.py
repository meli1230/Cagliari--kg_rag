from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

def rag_answer(question):
    # QUI colleghiamo la vera pipeline RAG (retrieval + Ollama)
    # per ora restituisce una risposta finta di test
    return f"Hai chiesto: '{question}' — qui arriverà la risposta del RAG."

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "")
    answer = rag_answer(question)
    return jsonify({"answer": answer})

if __name__ == "__main__":
    app.run(debug=True, port=5001)