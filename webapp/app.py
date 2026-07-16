from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

def rag_answer(question):
    return f"You asked the following question: '{question}' — here's where the RAG result will come from."
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