# Social Media & News Integration - Implementation Summary

**Date:** November 14, 2025  
**Status:** ✅ Complete - Ready for Testing

## Overview

Upgraded NexusTrader's data collection from basic title-only news scraping to enterprise-grade multi-source sentiment analysis, matching TradingAgents' sophistication while maintaining our streamlined 9-agent architecture.

## What Changed

### 1. **Alpha Vantage NEWS_SENTIMENT API** (News Harvester)

**Before:**
- pygooglenews: Title, link, date only
- No sentiment analysis
- No article summaries
- Generic Google News sources

**After:**
```python
# Returns rich data structure per article:
{
    "title": "Tesla Reports Record Q4 Earnings",
    "summary": "Full 200-word article summary...",  # NEW!
    "source": "Bloomberg",  # Verified source
    "overall_sentiment_score": 0.234567,  # -1 to +1 (NEW!)
    "overall_sentiment_label": "Somewhat-Bullish",  # NEW!
    "ticker_sentiment_score": 0.345678,  # Ticker-specific (NEW!)
    "ticker_sentiment_label": "Bullish",  # NEW!
    "relevance_score": 0.987654,  # How relevant to ticker (NEW!)
    "published": "20240115T160000",
    "url": "https://..."
}
```

**Key Benefits:**
- ✅ Pre-calculated sentiment (no LLM inference needed)
- ✅ Full article summaries (richer context)
- ✅ Relevance scoring (filters noise)
- ✅ Source credibility tracking
- ✅ 60 requests/min free tier (enough for MVP)

**Implementation:**
- File: `app/tools/news_tools.py`
- Function: `search_news_alpha_vantage(ticker, limit=50)`
- API Key: `ALPHA_VANTAGE_SENTIMENT_KEY` in `.env`
- Caching: 30 minutes TTL

---

### 2. **StockTwits Integration** (Sentiment Analyst)

**What is StockTwits?**
Finance-specific social media platform where traders share stock opinions with **pre-labeled sentiment** (Bullish/Bearish).

**API Details:**
```python
# Public API - No authentication required!
url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"

# Returns posts with pre-labeled sentiment:
{
    "text": "TSLA to the moon! 🚀 Strong quarter ahead",
    "sentiment": "Bullish",  # Pre-labeled by user!
    "created_at": "2024-01-15T10:30:00Z",
    "user": "trader_mike",
    "likes": 42
}
```

**Key Benefits:**
- ✅ **FREE - No API key required**
- ✅ **Pre-labeled sentiment** (users tag as Bullish/Bearish)
- ✅ Finance-focused community (high signal-to-noise)
- ✅ Real-time retail sentiment
- ✅ Engagement metrics (likes = credibility)

**Implementation:**
- File: `app/tools/social_media_tools.py`
- Function: `search_stocktwits(ticker, limit=30)`
- Returns: List of posts with sentiment labels
- Helper: `calculate_sentiment_metrics()` - computes bullish/bearish percentages

---

### 3. **Twitter/X Scraping** (Sentiment Analyst)

**Challenge:** Twitter API costs $100/month minimum.

**Solution:** `ntscraper` library scrapes public Nitter instances (Twitter mirrors).

**Implementation:**
```python
from ntscraper import Nitter

scraper = Nitter()
tweets = scraper.get_tweets(f"${ticker}", mode='term', number=20)

# Returns:
{
    "text": "Just bought more $TSLA shares...",
    "date": "2024-01-15",
    "likes": 1234,
    "retweets": 567,
    "user": "ElonFanboy",
    "link": "https://twitter.com/..."
}
```

**Key Benefits:**
- ✅ **FREE - No API key**
- ✅ Searches cashtags (`$TSLA`)
- ✅ Engagement metrics (likes/retweets)
- ✅ Real-time market buzz

**Limitations:**
- ⚠️ Slower than official API (web scraping)
- ⚠️ May break if Nitter/Twitter changes structure
- ⚠️ Rate limiting (use sparingly)

**Implementation:**
- File: `app/tools/social_media_tools.py`
- Function: `search_twitter(query, limit=20)`
- Dependency: `ntscraper` (installed via uv)

---

## Updated Agent Workflows

### **Sentiment Analyst** (`app/agents/analyst_team.py`)

**New Workflow:**
```python
def sentiment_analyst_agent(state: dict):
    ticker = state['ticker']
    
    # 1. Get StockTwits (pre-labeled sentiment)
    stocktwits_posts = search_stocktwits(ticker, limit=30)
    
    # 2. Get Twitter mentions
    twitter_posts = search_twitter(f"${ticker}", limit=20)
    
    # 3. Calculate sentiment metrics
    metrics = calculate_sentiment_metrics(stocktwits_posts)
    # Returns: {bullish_pct: 65%, bearish_pct: 25%, neutral_pct: 10%}
    
    # 4. Store in shared context
    shared_context.set(f'stocktwits_{ticker}', stocktwits_posts)
    shared_context.set(f'sentiment_metrics_{ticker}', metrics)
    
    # 5. Format for LLM
    prompt = f"""
    StockTwits: 65% Bullish, 25% Bearish (30 posts)
    Top posts: [list]
    
    Twitter: 20 tweets mentioning ${ticker}
    Top tweets: [list]
    
    Analyze sentiment trends, themes, risks...
    """
    
    # 6. LLM generates analysis
    return call_llm(prompt)
```

**Key Improvements:**
- ✅ Real social media data (not placeholders)
- ✅ Pre-calculated metrics (faster)
- ✅ Shared context for other agents
- ✅ Multi-source validation (StockTwits + Twitter)

---

### **News Harvester** (`app/agents/analyst_team.py`)

**New Workflow:**
```python
def news_harvester_agent(state: dict):
    ticker = state['ticker']
    
    # 1. Get news with sentiment from Alpha Vantage
    articles = search_news_alpha_vantage(ticker, limit=50)
    
    # 2. Store in shared context
    shared_context.set(f'news_articles_{ticker}', articles)
    
    # 3. Calculate aggregate sentiment
    avg_sentiment = sum(a['ticker_sentiment_score'] for a in articles) / len(articles)
    bullish_count = sum(1 for a in articles if 'Bullish' in a['ticker_sentiment_label'])
    
    # 4. Format for LLM (with summaries!)
    prompt = f"""
    News Summary (50 articles):
    Average Sentiment: {avg_sentiment:.2f}
    Bullish: {bullish_count}, Bearish: {bearish_count}
    
    Top 10 Articles:
    1. [Bullish] "Tesla Reports Record Earnings"
       Source: Bloomberg | Relevance: 0.98
       Summary: Tesla Inc reported record fourth-quarter...
    2. ...
    
    Analyze key catalysts, sentiment trends, risks...
    """
    
    # 5. LLM generates analysis
    return call_llm(prompt)
```

**Key Improvements:**
- ✅ Article summaries (not just titles)
- ✅ Pre-calculated sentiment scores
- ✅ Source credibility tracking
- ✅ Relevance filtering
- ✅ 50 articles vs 5 (10x more data)

---

## Comparison: Before vs After

| Feature | Before (pygooglenews + placeholders) | After (Alpha Vantage + StockTwits + Twitter) |
|---------|--------------------------------------|---------------------------------------------|
| **News Articles** | 5 titles only | 50 articles with summaries |
| **News Sentiment** | LLM infers from titles | Pre-calculated scores (-1 to +1) |
| **Social Media** | Placeholder functions | Real StockTwits + Twitter data |
| **Sentiment Labels** | None | Pre-labeled (Bullish/Bearish) |
| **Data Quality** | Low (minimal context) | High (rich summaries) |
| **Speed** | Slow (LLM sentiment) | Fast (pre-calculated) |
| **Cost** | Free | Free (all sources) |
| **Sources** | Google News only | Bloomberg, Reuters, CNBC, etc. |
| **Relevance** | All news | Filtered by relevance score |

---

## How It Matches TradingAgents

**TradingAgents Approach:**
- Uses Alpha Vantage for news (same API we now use)
- Uses pre-downloaded Reddit data (we use live StockTwits/Twitter)
- Multi-source validation (we now do this too)
- Pre-calculated sentiment (we now have this)

**Our Advantages:**
- ✅ Live social media data (not pre-downloaded)
- ✅ StockTwits pre-labeled sentiment (better than Reddit scraping)
- ✅ Twitter engagement metrics (credibility signals)
- ✅ All free (no API costs)

**Their Advantages:**
- ✅ Reddit historical data (we can't access live)
- ✅ 60 req/min Alpha Vantage partnership (we have same)

**Verdict:** We're now on par with TradingAgents for data quality, but with live social media instead of pre-downloaded Reddit archives.

---

## Technical Implementation Details

### File Changes

1. **`app/tools/news_tools.py`** - Complete rewrite
   - Removed: `pygooglenews` dependency
   - Added: `search_news_alpha_vantage()` with sentiment parsing
   - Kept: `search_news()` as legacy wrapper

2. **`app/tools/social_media_tools.py`** - Real implementations
   - Removed: Placeholder functions
   - Added: `search_stocktwits()` - StockTwits API client
   - Added: `search_twitter()` - ntscraper wrapper
   - Added: `calculate_sentiment_metrics()` - Bullish/bearish ratios
   - Kept: `search_reddit()` as placeholder (API restricted)

3. **`app/agents/analyst_team.py`** - Agent updates
   - Updated: `sentiment_analyst_agent()` - Multi-source social media
   - Updated: `news_harvester_agent()` - Alpha Vantage with summaries

4. **`pyproject.toml`** - Dependencies
   - Added: `requests` (HTTP client)
   - Added: `ntscraper` (Twitter scraping)

### Environment Variables

Add to `.env`:
```bash
ALPHA_VANTAGE_SENTIMENT_KEY=JE3C76KPWKW6DVTK  # Already set ✅
```

No additional keys needed - StockTwits and Twitter scraping are key-free!

---

## Testing Checklist

### Unit Tests
- [ ] `search_news_alpha_vantage()` returns valid articles
- [ ] `search_stocktwits()` returns posts with sentiment
- [ ] `search_twitter()` returns tweets (may be slow)
- [ ] `calculate_sentiment_metrics()` computes percentages correctly

### Integration Tests
- [ ] Sentiment Analyst stores data in shared_context
- [ ] News Harvester stores articles in shared_context
- [ ] LLM receives formatted prompts correctly
- [ ] State updates with sentiment_metrics and news_sentiment

### End-to-End Test
```bash
python test_debate_mechanism.py
```

**Expected Behavior:**
- Sentiment Analyst prints: "Found X StockTwits posts" and "Found Y tweets"
- News Harvester prints: "Found 50 articles for {ticker}"
- Both agents store data in shared_context
- Final analysis includes sentiment percentages and news summaries

---

## Performance Impact

**Expected Changes:**
- ⏱️ **Slower social media** (+10-15 sec for Twitter scraping)
- ⏱️ **Faster sentiment** (-5 sec, pre-calculated StockTwits labels)
- ⏱️ **Faster news** (-3 sec, no LLM inference on titles)
- 📊 **Net impact:** ~+5 seconds total (worth it for 10x data quality)

**Mitigation:**
- Caching (30 min TTL) - subsequent runs instant
- Parallel fetching (StockTwits + Twitter in parallel)
- Optional: Reduce Twitter limit to 10 tweets (save 5 sec)

---

## Future Enhancements (Post-MVP)

1. **Reddit Integration** - Requires API key ($$$) or pre-downloaded data
2. **YouTube Comments** - Finance YouTuber sentiment
3. **Google Trends** - Search interest momentum
4. **Discord/Telegram** - Crypto-focused for crypto stocks
5. **Sentiment Time Series** - Track sentiment changes over time
6. **Influencer Tracking** - Weight posts by follower count

---

## Rollback Plan (If Needed)

If new integrations cause issues:

1. **Revert news_tools.py:**
   ```python
   # Use legacy pygooglenews
   from pygooglenews import GoogleNews
   def search_news(query, limit=5):
       gn = GoogleNews()
       return gn.search(query)['entries'][:limit]
   ```

2. **Revert social_media_tools.py:**
   ```python
   # Use placeholder functions
   def search_stocktwits(ticker):
       return "Placeholder StockTwits data"
   ```

3. **Revert analyst_team.py:**
   - Use old sentiment_analyst_agent (simple placeholders)
   - Use old news_harvester_agent (title-only)

---

## Summary

✅ **Implemented:**
- Alpha Vantage NEWS_SENTIMENT API (50 articles with summaries + sentiment)
- StockTwits integration (pre-labeled bullish/bearish sentiment)
- Twitter/X scraping (real-time market buzz)
- Multi-source validation (news + social media)
- Sentiment metrics calculation (bullish/bearish percentages)

✅ **Benefits:**
- 10x more data (50 vs 5 news articles)
- Pre-calculated sentiment (faster, no LLM cost)
- Multi-source validation (reduces bias)
- Finance-focused social media (higher signal)
- All free APIs (no additional costs)

✅ **Ready for Testing:**
```bash
cd C:\Users\Madi\Documents\season_25-26\academic_25-26\FYP_multi_agent_trading\nexustrader\backend
python test_debate_mechanism.py
```

Expected: Rich sentiment analysis with actual social media data and news summaries! 🚀
