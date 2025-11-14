# In nexustrader/backend/app/tools/social_media_tools.py

import requests
from datetime import datetime
from ..utils.cache import cache_data

def search_stocktwits(ticker: str, limit: int = 30):
    """StockTwits placeholder - API closed to new registrations."""
    print(f"StockTwits disabled for {ticker} - API unavailable")
    return []

def search_twitter(query: str, limit: int = 20):
    """Twitter placeholder - scraping unreliable."""
    print(f"Twitter disabled for {query} - scraping unavailable")
    return []

def search_reddit(subreddit: str, query: str, limit: int = 10):
    """Reddit placeholder - not implemented."""
    print(f"Reddit disabled - API requires authentication")
    return []

def calculate_sentiment_metrics(posts: list, sentiment_field: str = 'sentiment'):
    """
    Calculate bullish/bearish ratios from posts with sentiment labels.
    Useful for StockTwits data which has pre-labeled sentiment.
    """
    if not posts:
        return {"bullish_pct": 0, "bearish_pct": 0, "neutral_pct": 0, "total": 0}
    
    bullish = sum(1 for p in posts if p.get(sentiment_field, '').lower() == 'bullish')
    bearish = sum(1 for p in posts if p.get(sentiment_field, '').lower() == 'bearish')
    total = len(posts)
    neutral = total - bullish - bearish
    
    return {
        "bullish_pct": round(bullish / total * 100, 1) if total > 0 else 0,
        "bearish_pct": round(bearish / total * 100, 1) if total > 0 else 0,
        "neutral_pct": round(neutral / total * 100, 1) if total > 0 else 0,
        "total": total,
        "bullish_count": bullish,
        "bearish_count": bearish,
    }
