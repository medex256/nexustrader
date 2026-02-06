# In nexustrader/backend/app/tools/news_tools.py
import os
import requests
from datetime import datetime, timedelta
from ..utils.cache import cache_data

@cache_data(ttl_seconds=1800)  # Cache for 30 minutes
def search_news_alpha_vantage(ticker: str, limit: int = 50, as_of: str = None, lookback_days: int = 7):
    """
    Searches Alpha Vantage NEWS_SENTIMENT API for articles with sentiment analysis.
    Returns news with pre-calculated sentiment scores, summaries, and relevance.
    """
    print(f"Searching Alpha Vantage news for {ticker}...")
    
    api_key = os.getenv('ALPHA_VANTAGE_SENTIMENT_KEY')
    if not api_key:
        print("Warning: ALPHA_VANTAGE_SENTIMENT_KEY not found in .env")
        return []
    
    # Calculate time range (last N days) with optional as-of date
    if as_of:
        try:
            end_date = datetime.fromisoformat(as_of)
        except ValueError:
            end_date = datetime.fromisoformat(as_of.split("T")[0])
    else:
        end_date = datetime.now()

    start_date = end_date - timedelta(days=lookback_days)
    
    # Format dates as YYYYMMDDTHHMM
    time_from = start_date.strftime("%Y%m%dT0000")
    time_to = end_date.strftime("%Y%m%dT2359")
    
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": ticker,
        "time_from": time_from,
        "time_to": time_to,
        "sort": "LATEST",
        "limit": limit,
        "apikey": api_key,
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "feed" not in data:
            print(f"No news feed in Alpha Vantage response: {data}")
            return []
        
        articles = []
        for item in data["feed"]:
            # Extract ticker-specific sentiment
            ticker_sentiment = None
            for ts in item.get("ticker_sentiment", []):
                if ts.get("ticker") == ticker:
                    ticker_sentiment = ts
                    break
            
            article = {
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "url": item.get("url", ""),
                "source": item.get("source", "Unknown"),
                "published": item.get("time_published", ""),
                "overall_sentiment_score": float(item.get("overall_sentiment_score", 0)),
                "overall_sentiment_label": item.get("overall_sentiment_label", "Neutral"),
                "ticker_sentiment_score": float(ticker_sentiment.get("ticker_sentiment_score", 0)) if ticker_sentiment else 0,
                "ticker_sentiment_label": ticker_sentiment.get("ticker_sentiment_label", "Neutral") if ticker_sentiment else "Neutral",
                "relevance_score": float(ticker_sentiment.get("relevance_score", 0)) if ticker_sentiment else 0,
            }
            articles.append(article)
        
        print(f"Found {len(articles)} articles for {ticker}")
        return articles
        
    except Exception as e:
        print(f"Error fetching Alpha Vantage news: {e}")
        return []

# Keep legacy function for backward compatibility
def search_news(query: str, limit: int = 5, as_of: str = None, lookback_days: int = 7):
    """
    Legacy function - redirects to Alpha Vantage news.
    """
    return search_news_alpha_vantage(query, limit, as_of=as_of, lookback_days=lookback_days)

