# In nexustrader/backend/app/tools/technical_analysis_tools.py
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for web server

import yfinance as yf
import pandas as pd
import mplfinance as mpf
import os
from datetime import datetime, timedelta
from ..utils.cache import cache_data


def _add_rsi(df: pd.DataFrame, length: int = 14) -> None:
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    df[f"RSI_{length}"] = 100 - (100 / (1 + rs))


def _add_sma(df: pd.DataFrame, length: int) -> None:
    df[f"SMA_{length}"] = df["Close"].rolling(window=length).mean()


def _add_macd(df: pd.DataFrame) -> None:
    ema_fast = df["Close"].ewm(span=12, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=26, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    df["MACD_12_26_9"] = macd
    df["MACDs_12_26_9"] = signal
    df["MACDh_12_26_9"] = hist


def _add_bollinger_bands(df: pd.DataFrame, length: int = 20, std_dev: float = 2.0) -> None:
    rolling_mean = df["Close"].rolling(window=length).mean()
    rolling_std = df["Close"].rolling(window=length).std()
    df[f"BBL_{length}_{std_dev}"] = rolling_mean - std_dev * rolling_std
    df[f"BBM_{length}_{std_dev}"] = rolling_mean
    df[f"BBU_{length}_{std_dev}"] = rolling_mean + std_dev * rolling_std
    band_width = df[f"BBU_{length}_{std_dev}"] - df[f"BBL_{length}_{std_dev}"]
    df[f"BBB_{length}_{std_dev}"] = band_width / rolling_mean.replace(0, pd.NA)
    df[f"BBP_{length}_{std_dev}"] = (df["Close"] - df[f"BBL_{length}_{std_dev}"]) / band_width.replace(0, pd.NA)

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
    Calculates a comprehensive set of technical indicators from the price data.
    Includes RSI, SMA, MACD, Bollinger Bands, and volume analysis.
    """
    print("Calculating technical indicators...")
    if price_data.empty:
        return {}

    df = price_data.copy()

    # RSI (14-period)
    _add_rsi(df, length=14)

    # Moving Averages
    _add_sma(df, length=20)
    _add_sma(df, length=50)

    # MACD (12, 26, 9)
    _add_macd(df)

    # Bollinger Bands (20-period, 2 std dev)
    _add_bollinger_bands(df, length=20, std_dev=2.0)

    # --- Collect latest values for all indicator columns ---
    latest = df.iloc[-1]
    indicator_tags = ['RSI', 'SMA', 'MACD', 'BBL', 'BBM', 'BBU', 'BBB', 'BBP']
    indicator_cols = [col for col in df.columns
                      if any(tag in col for tag in indicator_tags)]

    result = {}
    for col in indicator_cols:
        val = latest[col]
        if pd.notna(val):
            result[col] = round(float(val), 4)

    # --- Volume analysis ---
    if 'Volume' in df.columns and len(df) >= 20:
        vol_sma_20 = df['Volume'].rolling(window=20).mean().iloc[-1]
        latest_vol = float(df['Volume'].iloc[-1])
        if pd.notna(vol_sma_20) and vol_sma_20 > 0:
            result['Volume_SMA_20'] = round(float(vol_sma_20), 0)
            result['Volume_Ratio'] = round(latest_vol / float(vol_sma_20), 2)

    # --- Price context (5-day trend) ---
    if len(df) >= 5:
        last5_close = df['Close'].iloc[-5:]
        result['price_trend_5d_pct'] = round(
            float((last5_close.iloc[-1] / last5_close.iloc[0] - 1) * 100), 2
        )
        result['current_price'] = round(float(df['Close'].iloc[-1]), 2)

    return result

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
def get_chart_data_json(ticker: str, period: str = "6mo", as_of: str = None):
    """
    Returns OHLCV data formatted for lightweight charting libraries.
    """
    print(f"Fetching chart data for {ticker}...")
    stock = yf.Ticker(ticker)

    if as_of:
        try:
            end_date = datetime.fromisoformat(as_of)
        except ValueError:
            end_date = datetime.fromisoformat(as_of.split("T")[0])

        # Convert common yfinance period strings into a rough day window
        p = (period or "6mo").strip().lower()
        days = 180
        try:
            if p.endswith("d"):
                days = int(p[:-1])
            elif p.endswith("mo"):
                days = int(p[:-2]) * 30
            elif p.endswith("y"):
                days = int(p[:-1]) * 365
        except ValueError:
            days = 180

        start_date = end_date - timedelta(days=days)
        hist = stock.history(start=start_date, end=end_date + timedelta(days=1))
    else:
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
