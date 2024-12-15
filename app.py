import os
from flask import Flask, request, jsonify
import yfinance as yf

# Initialize Flask app
app = Flask(__name__)

@app.route("/")
def home():
    """Default route to confirm the app is running."""
    return "Flask app is running on Railway!"

@app.route("/stock")
def get_stock_price():
    """Endpoint to get the latest stock price."""
    ticker = request.args.get("ticker")
    if not ticker:
        return jsonify({"error": "Ticker symbol is required"}), 400

    try:
        # Fetch stock data from Yahoo Finance
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        if data.empty:
            return jsonify({"error": f"No data found for ticker '{ticker}'"}), 404
        price = data['Close'].iloc[-1]
        return jsonify({"ticker": ticker.upper(), "price": price})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/simulate_autocall", methods=["POST"])
def simulate_autocall():
    """Endpoint to simulate a 3-year autocallable product."""
    try:
        data = request.get_json()

        # Extract data from the POST request
        stocks = data.get("stocks", [])
        barrier = data.get("barrier", 0.5)
        if not stocks or not isinstance(stocks, list) or not barrier:
            return jsonify({"error": "Invalid input. Provide 'stocks' (list) and 'barrier' (float)."}), 400

        # Simulate scenarios (placeholder logic)
        results = {}
        for year in range(1, 4):
            scenarios = {
                f"year_{year}": "No autocall. Product continues."
            }
            if year == 2:
                scenarios[f"year_{year}"] = "Autocall triggered in year 2"
                break
        results.update(scenarios)

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Get the port dynamically from the environment or default to 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
