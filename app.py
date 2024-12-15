from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "Flask app is running!"

@app.route("/stock")
def get_stock():
    ticker = request.args.get("ticker")
    if not ticker:
        return jsonify({"error": "Ticker symbol required"}), 400
    return jsonify({"ticker": ticker, "price": 123.45})  # Placeholder response

if __name__ == "__main__":
    # Set the host and port dynamically
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
