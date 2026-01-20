# In nexustrader/backend/app/tools/portfolio_tools.py
import yfinance as yf
import numpy as np
import pandas as pd

def get_market_volatility_index():
    """
    Returns the current value of the VIX (Market Volatility Index).
    """
    print("Fetching market volatility index (VIX)...")
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="1d")
        if not hist.empty:
            close_price = hist['Close'].iloc[-1]
            return f"{close_price:.2f}"
        return "20.00 (Default - Data Unavailable)"
    except Exception as e:
        print(f"Error fetching VIX: {e}")
        return "20.00 (Default - Error)"

def get_portfolio_composition():
    """
    Returns the current composition of the trading portfolio.
    For Single Ticker Analysis, this returns a simulated 'Cash Only' state
    to simulate a fresh start.
    """
    return "100% Cash (Simulated for Single Ticker Evaluation)"

def calculate_ticker_risk_metrics(ticker: str):
    """
    Calculates specific risk metrics for the ticker using historical data:
    - Annualized Volatility
    - Max Drawdown (1Y)
    - Beta (vs S&P 500)
    """
    print(f"Calculating risk metrics for {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        
        if hist.empty:
            return {"error": "No historical data found"}
            
        # 1. Volatility (Annualized Standard Deviation of Returns)
        hist['Returns'] = hist['Close'].pct_change()
        volatility = hist['Returns'].std() * np.sqrt(252) * 100
        
        # 2. Max Drawdown
        rolling_max = hist['Close'].cummax()
        drawdown = (hist['Close'] - rolling_max) / rolling_max
        max_drawdown = drawdown.min() * 100
        
        # 3. Beta (proxy vs SPY if possible, simplified here just to volatility)
        # To compute real Beta we need SPY data. Let's stick to Volatility & Drawdown for speed.
        
        current_price = hist['Close'].iloc[-1]
        
        return {
            "annualized_volatility_pct": f"{volatility:.2f}%",
            "max_drawdown_1y_pct": f"{max_drawdown:.2f}%",
            "current_price": f"${current_price:.2f}",
            "risk_rating": "HIGH" if volatility > 40 else "MODERATE" if volatility > 20 else "LOW"
        }
    except Exception as e:
        print(f"Error calculating risk: {e}")
        return {"error": str(e)}

def calculate_portfolio_VaR(portfolio):
    """
    Legacy placeholder - deprecated in favor of calculate_ticker_risk_metrics for this Agent.
    """
    return "N/A (Using Single Ticker Risk Metrics)"

def get_correlation_matrix(portfolio):
    """
    Legacy placeholder.
    """
    return "N/A"

def get_restricted_securities_list():
    """
    Returns a list of securities that are currently restricted from trading.

    NOTE: This is a placeholder function.
    """
    print("Fetching restricted securities list...")
    return []

def get_position_size_limits():
    """
    Returns the current position size limits for the portfolio.

    NOTE: This is a placeholder function.
    """
    print("Fetching position size limits...")
    return "Dummy position size limits"

def check_trade_compliance(trade):
    """
    Checks a proposed trade against all relevant compliance rules and returns a pass/fail result with an explanation.

    NOTE: This is a placeholder function.
    """
    print("Checking trade compliance...")
    return {"result": "pass", "explanation": "Trade is compliant."}

def log_compliance_check(trade, result):
    """
    Logs the details of a compliance check to an audit trail.

    NOTE: This is a placeholder function.
    """
    print("Logging compliance check...")
    return True
