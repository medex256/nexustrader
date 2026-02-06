# In nexustrader/backend/app/tools/technical_analysis_tools.py
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for web server

import yfinance as yf
import pandas_ta as ta
import mplfinance as mpf
import os
from datetime import datetime, timedelta
from ..utils.cache import cache_data

@cache_data(ttl_seconds=3600)  # Cache for 1 hour
def get_historical_price_data(ticker: str, period: str = "1y", as_of: str = None):
    """
    Returns the historical price and volume data for the stock.
    """
    print(f"Fetching historical price data for {ticker}...")
    stock = yf.Ticker(ticker)
    if as_of:
        try:
            end_date = datetime.fromisoformat(as_of)
        except ValueError:
            end_date = datetime.fromisoformat(as_of.split("T")[0])

        start_date = end_date - timedelta(days=365)
        hist = stock.history(start=start_date, end=end_date + timedelta(days=1))
    else:
        hist = stock.history(period=period)
    return hist

def calculate_technical_indicators(price_data):
    """
    Calculates a set of technical indicators from the price data.
    """
    print("Calculating technical indicators...")
    if price_data.empty:
        return {}
        
    # Calculate RSI
    price_data.ta.rsi(append=True)
    
    # Calculate moving averages
    price_data.ta.sma(length=20, append=True)
    price_data.ta.sma(length=50, append=True)
    
    # Return the latest indicator values
    latest_indicators = price_data.iloc[-1][[col for col in price_data.columns if 'RSI' in col or 'SMA' in col]]
    
    return latest_indicators.to_dict()

def plot_stock_chart(price_data, ticker: str):
    """
    Generates a stock chart with the price data and technical indicators.
    """
    print("Plotting stock chart...")
    if price_data.empty:
        return None

    # Ensure the output directory exists
    output_dir = "charts"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Create the plot with moving averages
    chart_file = os.path.join(output_dir, f"{ticker}_chart.png")
    mpf.plot(
        price_data,
        type='candle',
        style='charles',
        title=f"{ticker} Stock Chart",
        ylabel='Price ($)',
        mav=(20, 50),
        volume=True,
        savefig=chart_file
    )
    
    return chart_file

@cache_data(ttl_seconds=3600)
def get_chart_data_json(ticker: str, period: str = "6mo"):
    """
    Returns OHLCV data formatted for lightweight charting libraries.
    """
    print(f"Fetching chart data for {ticker}...")
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)
    if hist.empty:
        return []

    # Ensure we have the required columns
    hist = hist[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

    # Reset index to access dates
    hist.reset_index(inplace=True)

    # Format for Lightweight Charts: time (YYYY-MM-DD), open, high, low, close, volume
    chart_data = []
    for _, row in hist.iterrows():
        chart_data.append({
            "time": row['Date'].strftime('%Y-%m-%d'),
            "open": round(float(row['Open']), 4),
            "high": round(float(row['High']), 4),
            "low": round(float(row['Low']), 4),
            "close": round(float(row['Close']), 4),
            "volume": int(row['Volume']),
        })

    return chart_data
