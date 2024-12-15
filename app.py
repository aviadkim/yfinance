from flask import Flask, request, jsonify
import yfinance as yf

app = Flask(__name__)

# Endpoint to get live stock price
@app.route('/stock', methods=['GET'])
def get_stock_price():
    ticker = request.args.get('ticker')  # Get the ticker from query parameters
    if not ticker:
        return jsonify({"error": "Ticker symbol is required"}), 400

    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        price = data['Close'].iloc[-1]
        return jsonify({"ticker": ticker, "price": price})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to simulate scenarios
@app.route('/simulate', methods=['POST'])
def simulate_autocallable():
    try:
        data = request.get_json()
        stocks = data['stocks']
        initial_prices = data['initial_prices']
        barrier = data['barrier']

        results = {}
        for i, stock in enumerate(stocks):
            performance = initial_prices[i] * (1 - barrier)
            results[stock] = {
                "initial_price": initial_prices[i],
                "barrier_price": performance,
                "description": f"Barrier price for {stock} is {performance}"
            }

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
