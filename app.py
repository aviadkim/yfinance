import os
from flask import Flask, request, jsonify
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np

app = Flask(__name__)

def calculate_quarterly_coupon(stock_prices, barrier_level):
    """
    Calculate if quarterly coupon should be paid based on barrier level
    """
    all_above_barrier = all(price >= barrier_level for price in stock_prices)
    return {
        "coupon_paid": all_above_barrier,
        "reason": "All stocks above barrier" if all_above_barrier else "One or more stocks below barrier"
    }

def get_historical_data(ticker, start_date, end_date):
    """
    Get historical stock data with error handling
    """
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(start=start_date, end=end_date)
        if data.empty:
            raise ValueError(f"No data found for {ticker}")
        return data['Close']
    except Exception as e:
        raise ValueError(f"Error fetching data for {ticker}: {str(e)}")

@app.route("/")
def home():
    return "Autocall Product Simulation API is running!"

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
            "currency": info.get('currency', 'USD')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/simulate_autocall", methods=["POST"])
def simulate_autocall():
    try:
        data = request.get_json()
        
        # Validate input
        stocks = data.get("stocks", [])
        barrier = data.get("barrier", 0.5)
        initial_investment = data.get("initial_investment", 100000)
        coupon_rate = data.get("coupon_rate", 0.08)  # 8% annual coupon
        
        if len(stocks) != 3:
            return jsonify({"error": "Exactly 3 stock tickers are required"}), 400
            
        # Get initial prices and dates
        start_date = datetime.now() - timedelta(days=1)
        initial_prices = {}
        
        for ticker in stocks:
            try:
                stock_data = get_historical_data(ticker, start_date, datetime.now())
                initial_prices[ticker] = stock_data.iloc[-1]
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
        
        # Simulate quarterly observations (12 quarters over 3 years)
        quarters = []
        barrier_prices = {ticker: price * barrier for ticker, price in initial_prices.items()}
        
        for quarter in range(1, 13):
            # Simulate price movement (simplified for demo)
            current_prices = {
                ticker: price * (1 + np.random.normal(0, 0.1))
                for ticker, price in initial_prices.items()
            }
            
            # Calculate coupon payment
            coupon_result = calculate_quarterly_coupon(
                [price for price in current_prices.values()],
                min(barrier_prices.values())
            )
            
            quarter_data = {
                "quarter": quarter,
                "year": (quarter - 1) // 4 + 1,
                "prices": current_prices,
                "coupon_paid": coupon_result["coupon_paid"],
                "coupon_amount": initial_investment * (coupon_rate / 4) if coupon_result["coupon_paid"] else 0,
                "reason": coupon_result["reason"]
            }
            
            # Check for autocall condition (every 4 quarters)
            if quarter % 4 == 0:
                all_above_initial = all(
                    current_prices[ticker] >= initial_prices[ticker]
                    for ticker in stocks
                )
                if all_above_initial:
                    quarter_data["autocall"] = True
                    quarter_data["redemption_amount"] = initial_investment
                    quarters.append(quarter_data)
                    break
            
            quarters.append(quarter_data)
        
        return jsonify({
            "initial_investment": initial_investment,
            "barrier_level": barrier,
            "annual_coupon_rate": coupon_rate,
            "initial_prices": initial_prices,
            "barrier_prices": barrier_prices,
            "quarterly_results": quarters
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)