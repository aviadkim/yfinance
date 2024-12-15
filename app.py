import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "Flask YFinance API is running!"

@app.route("/stock", methods=["GET"])
def get_stock_price():
    ticker = request.args.get("ticker")
    if not ticker:
        return jsonify({"error": "Ticker symbol is required"}), 400
    
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        if data.empty:
            return jsonify({"error": f"No data found for ticker '{ticker}'"}), 404
        
        info = stock.info
        current_price = data['Close'].iloc[-1]
        
        return jsonify({
            "ticker": ticker.upper(),
            "price": current_price,
            "company_name": info.get('longName', ''),
            "currency": info.get('currency', 'USD'),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def calculate_coupon_payment(current_prices, barrier_prices, coupon_rate, initial_investment):
    """Calculate if coupon should be paid based on current prices and barrier"""
    all_above_barrier = all(
        current >= barrier for current, barrier in zip(current_prices, barrier_prices)
    )
    return {
        "paid": all_above_barrier,
        "amount": initial_investment * (coupon_rate / 4) if all_above_barrier else 0,
        "reason": "All stocks above barrier" if all_above_barrier else "One or more stocks below barrier"
    }

@app.route("/simulate_autocall", methods=["POST"])
def simulate_autocall():
    try:
        data = request.get_json()
        
        # Validate input
        stocks = data.get("stocks", [])
        barrier = data.get("barrier", 0.5)  # 50% barrier
        initial_investment = data.get("initial_investment", 100000)  # 100,000 default investment
        coupon_rate = data.get("coupon_rate", 0.08)  # 8% annual coupon rate
        
        if len(stocks) != 3:
            return jsonify({"error": "Exactly 3 stock tickers are required"}), 400
        
        # Get current stock prices
        initial_prices = {}
        try:
            for ticker in stocks:
                stock = yf.Ticker(ticker)
                data = stock.history(period="1d")
                if data.empty:
                    return jsonify({"error": f"No data found for ticker '{ticker}'"}), 404
                initial_prices[ticker] = data['Close'].iloc[-1]
        except Exception as e:
            return jsonify({"error": f"Error fetching stock data: {str(e)}"}), 500
        
        # Calculate barrier prices
        barrier_prices = {ticker: price * barrier for ticker, price in initial_prices.items()}
        
        # Simulate 12 quarters (3 years)
        quarterly_results = []
        for quarter in range(1, 13):
            # Simulate price movements using random walk
            current_prices = {
                ticker: price * (1 + np.random.normal(0, 0.1))  # 10% volatility
                for ticker, price in initial_prices.items()
            }
            
            # Calculate coupon payment
            coupon_result = calculate_coupon_payment(
                list(current_prices.values()),
                list(barrier_prices.values()),
                coupon_rate,
                initial_investment
            )
            
            quarter_data = {
                "quarter": quarter,
                "year": (quarter - 1) // 4 + 1,
                "prices": {ticker: round(price, 2) for ticker, price in current_prices.items()},
                "coupon_paid": coupon_result["paid"],
                "coupon_amount": round(coupon_result["amount"], 2),
                "reason": coupon_result["reason"]
            }
            
            # Check for autocall condition on observation dates (end of each year)
            if quarter % 4 == 0:
                all_above_initial = all(
                    current_prices[ticker] >= initial_prices[ticker]
                    for ticker in stocks
                )
                if all_above_initial:
                    quarter_data["autocall_triggered"] = True
                    quarter_data["redemption_amount"] = initial_investment
                    quarterly_results.append(quarter_data)
                    break
            
            quarterly_results.append(quarter_data)
        
        result = {
            "initial_investment": initial_investment,
            "barrier_level": barrier,
            "annual_coupon_rate": coupon_rate,
            "initial_prices": {ticker: round(price, 2) for ticker, price in initial_prices.items()},
            "barrier_prices": {ticker: round(price, 2) for ticker, price in barrier_prices.items()},
            "quarterly_results": quarterly_results
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)