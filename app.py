import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/')
def home():
    try:
        return jsonify({
            "status": "success",
            "message": "YFinance API is running",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route("/stock", methods=["GET"])
def get_stock_price():
    ticker = request.args.get("ticker")
    if not ticker:
        return jsonify({"error": "Ticker symbol is required"}), 400
    
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        
        # אם הריק, ננסה "5d" למקרה שהיום אין מסחר:
        if data.empty:
            data = stock.history(period="5d")
            if data.empty:
                return jsonify({"error": f"No data found for ticker '{ticker}'"}), 404

        # החל מ-0.2.50 אפשר להשתמש ב-get_info(); אם זה לא עובד, fallback ל-info
        try:
            info = stock.get_info()
        except:
            info = getattr(stock, 'info', {})
        
        current_price = float(data['Close'].iloc[-1])
        
        response = {
            "ticker": ticker.upper(),
            "price": current_price,
            "timestamp": datetime.now().isoformat()
        }

        # אם יש currency במידע
        currency = info.get('currency')
        if currency:
            response["currency"] = currency

        # אם יש שם חברה
        if 'longName' in info:
            response["company_name"] = info['longName']
            
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def calculate_coupon_payment(prices, barrier_levels, coupon_rate, initial_investment):
    try:
        all_above_barrier = all(
            price >= barrier for price, barrier in zip(prices, barrier_levels)
        )
        coupon_amount = initial_investment * (coupon_rate / 4) if all_above_barrier else 0
        
        return {
            "paid": all_above_barrier,
            "amount": round(coupon_amount, 2),
            "reason": "All stocks above barrier" if all_above_barrier else "One or more stocks below barrier"
        }
    except Exception as e:
        raise ValueError(f"Error in coupon calculation: {str(e)}")

@app.route("/simulate_autocall", methods=["POST"])
def simulate_autocall():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        # Extract and validate input parameters
        stocks = data.get("stocks", [])
        barrier = float(data.get("barrier", 0.5))  # 50% barrier
        initial_investment = float(data.get("initial_investment", 100000))
        coupon_rate = float(data.get("coupon_rate", 0.08))  # 8% annual

        if len(stocks) != 3:
            return jsonify({"error": "Exactly 3 stock tickers are required"}), 400
        
        if not (0 < barrier < 1):
            return jsonify({"error": "Barrier must be between 0 and 1"}), 400
        
        if not (0 < coupon_rate < 1):
            return jsonify({"error": "Coupon rate must be between 0 and 1"}), 400

        # Fetch current stock prices
        initial_prices = {}
        current_prices = {}
        try:
            for ticker in stocks:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="1d")
                if hist.empty:
                    hist = stock.history(period="5d")
                    if hist.empty:
                        return jsonify({"error": f"No data found for {ticker}"}), 404
                price = float(hist['Close'].iloc[-1])
                initial_prices[ticker] = price
                current_prices[ticker] = price
        except Exception as e:
            return jsonify({"error": f"Error fetching stock data: {str(e)}"}), 500

        # Calculate barrier prices
        barrier_prices = {ticker: price * barrier for ticker, price in initial_prices.items()}

        # Simulate quarters
        quarters = []
        simulation_completed = False
        
        for quarter in range(1, 13):  # 3 years = 12 quarters
            # Simulate price movements (10% volatility)
            simulated_prices = {
                ticker: price * (1 + np.random.normal(0, 0.1))
                for ticker, price in current_prices.items()
            }
            
            # Calculate coupon
            coupon_result = calculate_coupon_payment(
                list(simulated_prices.values()),
                list(barrier_prices.values()),
                coupon_rate,
                initial_investment
            )

            quarter_data = {
                "quarter": quarter,
                "year": (quarter - 1) // 4 + 1,
                "prices": {t: round(p, 2) for t, p in simulated_prices.items()},
                "coupon_paid": coupon_result["paid"],
                "coupon_amount": coupon_result["amount"],
                "reason": coupon_result["reason"]
            }

            # Check autocall condition (every 4th quarter)
            if quarter % 4 == 0:
                all_above_initial = all(
                    simulated_prices[ticker] >= initial_prices[ticker]
                    for ticker in stocks
                )
                if all_above_initial:
                    quarter_data["autocall_triggered"] = True
                    quarter_data["redemption_amount"] = initial_investment
                    simulation_completed = True

            quarters.append(quarter_data)
            current_prices = simulated_prices

            if simulation_completed:
                break

        response = {
            "simulation_id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "initial_investment": initial_investment,
            "barrier_level": barrier,
            "annual_coupon_rate": coupon_rate,
            "initial_prices": {t: round(p, 2) for t, p in initial_prices.items()},
            "barrier_prices": {t: round(p, 2) for t, p in barrier_prices.items()},
            "quarterly_results": quarters,
            "simulation_completed": simulation_completed
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({
            "error": "Simulation failed",
            "details": str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
