from flask import Flask, render_template, jsonify
import random

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.get("/random")
def random_number():
    return jsonify(number=random.randint(1, 1_000_000))

if __name__ == "__main__":
    # Start the server
    app.run(host="127.0.0.1", port=8000, debug=True)
