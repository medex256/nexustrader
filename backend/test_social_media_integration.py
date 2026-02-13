"""Quick test to verify News, StockTwits, and Twitter integrations.

Run this before full system test to catch API issues early.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 80)
print("TESTING SOCIAL MEDIA & NEWS INTEGRATIONS")
print("=" * 80)

# Test 1: News (Finnhub)
print("\n[1/3] Testing Finnhub company news...")
try:
    from app.tools.news_tools import search_news
    
    articles = search_news("TSLA", limit=5)
    
    if articles:
        print(f"✅ SUCCESS: Retrieved {len(articles)} articles")
        print(f"   Sample: {articles[0]['title'][:80]}...")
        print(f"   Tone: {articles[0]['ticker_sentiment_label']} ({articles[0]['ticker_sentiment_score']:.2f})")
    else:
        print("⚠️  WARNING: No articles returned (check API key or rate limit)")
except Exception as e:
    print(f"❌ FAILED: {e}")

# Test 2: StockTwits
print("\n[2/3] Testing StockTwits API...")
try:
    from app.tools.social_media_tools import search_stocktwits, calculate_sentiment_metrics
    
    posts = search_stocktwits("TSLA", limit=10)
    
    if posts:
        metrics = calculate_sentiment_metrics(posts)
        print(f"✅ SUCCESS: Retrieved {len(posts)} posts")
        print(f"   Bullish: {metrics['bullish_pct']}% | Bearish: {metrics['bearish_pct']}%")
        print(f"   Sample: [{posts[0]['sentiment'] or 'Neutral'}] {posts[0]['text'][:60]}...")
    else:
        print("⚠️  WARNING: No posts returned (check ticker or API)")
except Exception as e:
    print(f"❌ FAILED: {e}")

# Test 3: Twitter/X Scraping
print("\n[3/3] Testing Twitter/X scraping (may be slow)...")
try:
    from app.tools.social_media_tools import search_twitter
    
    tweets = search_twitter("$TSLA", limit=5)
    
    if tweets:
        print(f"✅ SUCCESS: Retrieved {len(tweets)} tweets")
        print(f"   Sample: {tweets[0]['text'][:60]}...")
        print(f"   Engagement: {tweets[0]['likes']} likes, {tweets[0]['retweets']} retweets")
    else:
        print("⚠️  WARNING: No tweets returned (Nitter may be down)")
except ImportError:
    print("⚠️  SKIPPED: ntscraper not installed (run: uv add ntscraper)")
except Exception as e:
    print(f"❌ FAILED: {e}")
    print("   Note: Twitter scraping can be unreliable (Nitter instances may be down)")

# Summary
print("\n" + "=" * 80)
print("INTEGRATION TEST COMPLETE")
print("=" * 80)
print("\nNext Steps:")
print("1. If all tests passed: Run full system test with `python test_debate_mechanism.py`")
print("2. If News failed: Check FINHUB_API_KEY/FINNHUB_API_KEY in .env")
print("3. If Twitter failed: It's optional - system will work without it")
print("4. If StockTwits failed: Check internet connection or ticker symbol")
print("=" * 80)
