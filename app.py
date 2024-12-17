import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

app = Flask(__name__)
CORS(app)

class FinanceAnalyzer:
    @staticmethod
    def get_stock_info(ticker):
        """Get current stock information with error handling"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            
            if hist.empty:
                return {"error": f"No data found for {ticker}"}
            
            current_price = hist['Close'].iloc[-1]
            year_high = hist['High'].max()
            year_low = hist['Low'].min()
            yearly_return = ((current_price - hist['Open'].iloc[0]) / hist['Open'].iloc[0]) * 100
            volatility = hist['Close'].pct_change().std() * np.sqrt(252)
            
            # Get company info safely
            try:
                info = stock.get_info()
            except:
                info = {}
            
            return {
                "ticker": ticker,
                "company_name": info.get('longName', ticker),
                "current_price": round(current_price, 2),
                "year_high": round(year_high, 2),
                "year_low": round(year_low, 2),
                "yearly_return": round(yearly_return, 2),
                "volatility": round(volatility * 100, 2),
                "currency": info.get('currency', 'USD'),
                "sector": info.get('sector', 'Unknown'),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": f"Error fetching data for {ticker}: {str(e)}"}

    @staticmethod
    def analyze_structured_product(tickers, initial_investment, barrier, coupon_rate, term_years):
        """Analyze structured product with multiple stocks"""
        try:
            stocks_data = {}
            for ticker in tickers:
                stock_info = FinanceAnalyzer.get_stock_info(ticker)
                if "error" in stock_info:
                    return {"error": stock_info["error"]}
                stocks_data[ticker] = stock_info
            
            barrier_levels = {
                ticker: data["current_price"] * barrier 
                for ticker, data in stocks_data.items()
            }
            
            quarterly_coupon = (coupon_rate * initial_investment) / 4
            total_quarters = term_years * 4
            max_return = quarterly_coupon * total_quarters
            max_return_pct = (max_return / initial_investment) * 100
            worst_case_loss = (barrier - 1) * initial_investment
            
            return {
                "analysis_timestamp": datetime.now().isoformat(),
                "product_details": {
                    "initial_investment": initial_investment,
                    "barrier_level": f"{barrier * 100}%",
                    "coupon_rate": f"{coupon_rate * 100}%",
                    "term": f"{term_years} years",
                    "payment_frequency": "Quarterly"
                },
                "underlying_stocks": stocks_data,
                "barrier_levels": {t: round(b, 2) for t, b in barrier_levels.items()},
                "scenarios": {
                    "best_case": {
                        "description": "All stocks remain above barrier",
                        "quarterly_coupon": round(quarterly_coupon, 2),
                        "annual_return": f"{round(coupon_rate * 100, 2)}%",
                        "total_return": round(max_return, 2),
                        "return_percentage": f"{round(max_return_pct, 2)}%"
                    },
                    "worst_case": {
                        "description": "One or more stocks fall below barrier",
                        "maximum_loss": round(abs(worst_case_loss), 2),
                        "loss_percentage": f"{round((worst_case_loss/initial_investment) * 100, 2)}%"
                    }
                }
            }
        except Exception as e:
            return {"error": f"Error analyzing structured product: {str(e)}"}

# API Routes
@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/stock/<ticker>')
def get_stock(ticker):
    """Get stock information"""
    return jsonify(FinanceAnalyzer.get_stock_info(ticker))

@app.route('/stocks', methods=['POST'])
def get_multiple_stocks():
    """Get information for multiple stocks"""
    data = request.get_json()
    if not data or 'tickers' not in data:
        return jsonify({"error": "Please provide tickers list"}), 400
        
    results = {}
    for ticker in data['tickers']:
        results[ticker] = FinanceAnalyzer.get_stock_info(ticker)
    return jsonify(results)

@app.route('/analyze_product', methods=['POST'])
def analyze_product():
    """Analyze structured product"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    required_fields = ['tickers', 'initial_investment', 'barrier', 'coupon_rate', 'term_years']
    if not all(field in data for field in required_fields):
        return jsonify({"error": f"Missing required fields. Please provide: {', '.join(required_fields)}"}), 400
    
    if len(data['tickers']) != 3:
        return jsonify({"error": "Please provide exactly 3 stock tickers"}), 400
    
    return jsonify(FinanceAnalyzer.analyze_structured_product(
        tickers=data['tickers'],
        initial_investment=float(data['initial_investment']),
        barrier=float(data['barrier']),
        coupon_rate=float(data['coupon_rate']),
        term_years=int(data['term_years'])
    ))

if __name__ == "__main__":
    # For local development only - Railway will use gunicorn
    app.run(host="0.0.0.0", port=8080)
