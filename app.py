import os
from flask import Flask, request, jsonify, send_file  # Note: Added send_file import
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def get_stock_info_safe(ticker_symbol):
    """Safely get stock information using multiple fallback methods"""
    stock = yf.Ticker(ticker_symbol)
    
    # Get historical data first (most reliable)
    # Changed from '2d' to '1d' as '2d' is not valid anymore
    hist = stock.history(period="1d")
    if hist.empty:
        hist = stock.history(period="5d")  # Try longer period if 1d is empty
        if hist.empty:
            raise ValueError(f"No historical data found for {ticker_symbol}")
    
    current_price = float(hist['Close'].iloc[-1])
    
    # Try different methods to get additional info
    try:
        info = stock.get_info()  # New method
    except:
        try:
            info = stock.fast_info  # Alternative method
        except:
            info = {}  # Fallback to empty dict if both fail
    
    return {
        "price": current_price,
        "company_name": info.get('longName', ticker_symbol),
        "currency": info.get('currency', 'USD'),
        "data_timestamp": hist.index[-1].isoformat(),
        "last_price": current_price,
        "day_high": float(hist['High'].iloc[-1]),
        "day_low": float(hist['Low'].iloc[-1]),
        "volume": float(hist['Volume'].iloc[-1]) if 'Volume' in hist else None
    }

@app.route('/')
def home():
    print("Home route accessed")
    try:
        return jsonify({
            "status": "success",
            "message": "YFinance API is running",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error in home route: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/health')
def health_check():
    print("Health check route accessed")
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route("/stock", methods=["GET"])
def get_stock_price():
    print("Stock route accessed")
    ticker = request.args.get("ticker")
    if not ticker:
        return jsonify({"error": "Ticker symbol is required"}), 400
    
    print(f"Getting data for ticker: {ticker}")
    try:
        stock_data = get_stock_info_safe(ticker)
        
        response = {
            "ticker": ticker.upper(),
            **stock_data,
            "request_timestamp": datetime.now().isoformat()
        }
            
        return jsonify(response)
    except Exception as e:
        print(f"Error getting stock data: {str(e)}")
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
    print("Simulate autocall route accessed")
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

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

        # Fetch current stock prices with improved error handling
        initial_prices = {}
        current_prices = {}
        stock_info = {}
        
        for ticker in stocks:
            try:
                info = get_stock_info_safe(ticker)
                price = info['price']
                initial_prices[ticker] = price
                current_prices[ticker] = price
                stock_info[ticker] = info
            except Exception as e:
                print(f"Error fetching data for {ticker}: {str(e)}")
                return jsonify({"error": f"Error fetching data for {ticker}: {str(e)}"}), 500

        # Calculate barrier prices
        barrier_prices = {ticker: price * barrier for ticker, price in initial_prices.items()}
        quarters = []
        simulation_completed = False
        
        for quarter in range(1, 13):  # 3 years = 12 quarters
            # Simulate price movements
            simulated_prices = {
                ticker: price * (1 + np.random.normal(0, 0.1))  # 10% volatility
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
            "stock_info": stock_info,
            "initial_prices": {t: round(p, 2) for t, p in initial_prices.items()},
            "barrier_prices": {t: round(p, 2) for t, p in barrier_prices.items()},
            "quarterly_results": quarters,
            "simulation_completed": simulation_completed
        }

        return jsonify(response)

    except Exception as e:
        print(f"Error in simulation: {str(e)}")
        return jsonify({
            "error": "Simulation failed",
            "details": str(e)
        }), 500

# ------------------ NEW ROUTES FOR PLUGIN FILES -------------------
@app.route('/ai-plugin.json')
def serve_ai_plugin():
    return send_file('ai-plugin.json', mimetype='application/json')

@app.route('/openapi.yaml')
def serve_openapi():
    return send_file('openapi.yaml', mimetype='text/yaml')
# -------------------------------------------------------------------

if __name__ == "__main__":
    # For local development only - Railway will use gunicorn
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
