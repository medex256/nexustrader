# Finnhub News API Features & Implementation

**Implementation Date**: February 12, 2026  
**Purpose**: Document Finnhub company news capabilities supporting NexusTrader FYP evaluation

---

## Executive Summary

We switched from AlphaVantage NEWS_SENTIMENT to **Finnhub Company News** (`/company-news`) for historical news retrieval due to AlphaVantage's restrictive 25 requests/day free tier. Finnhub provides **1 year of historical company news** on the free plan with **60 calls/minute**, making it viable for reproducible batch experiments at FYP scale.

**Key Design Decisions:**
- **Persistent caching** (`ttl_seconds=0`): All Finnhub responses cached forever for reproducibility across runs
- **Unified 14-day lookback**: Single news window for all horizons (was horizon-dependent 7/14/30 days)
- **Heuristic sentiment proxy**: Deterministic keyword-based tone scoring (Finnhub free lacks native sentiment)

---

## Finnhub Company News Endpoint

### Base Specifications
```
URL: https://finnhub.io/api/v1/company-news
Method: GET
Auth: API token via ?token= param or X-Finnhub-Token header
```

### Free Tier Limits
| Feature | Free Plan |
|---------|-----------|
| Historical range | **1 year** (rolling window from current date) |
| Rate limit | **60 calls/minute** |
| Daily hard cap | None (minute-based only) |
| Date filtering | Yes (`from` & `to` params in YYYY-MM-DD) |
| Sentiment data | ❌ No (Premium feature via NEWS_SENTIMENT Premium) |

### Request Parameters
```python
params = {
    "symbol": "AAPL",           # Required: US ticker
    "from": "2025-02-01",       # Required: YYYY-MM-DD
    "to": "2025-02-12",         # Required: YYYY-MM-DD (inclusive)
    "token": api_key            # Required
}
```

### Response Schema
```python
[
    {
        "category": "company news",
        "datetime": 1707782400,         # UNIX seconds (UTC)
        "headline": "Apple Vision Pro...",
        "id": 123456,
        "image": "https://...",
        "related": "AAPL",
        "source": "Reuters",
        "summary": "Apple announced...",
        "url": "https://..."
    },
    ...
]
```

**Field Notes:**
- `datetime`: UNIX timestamp (seconds, not ms) – convert to ISO-8601 for provenance
- `headline`: Primary title
- `summary`: Article excerpt (length varies; often 100-300 chars)
- `source`: Publisher/wire service name
- `related`: Comma-separated tickers mentioned (may differ from query symbol)
- No native sentiment scores/labels

---

## Implementation in NexusTrader

### 1. News Tool (`backend/app/tools/news_tools.py`)

**Core Function:**
```python
@cache_data(ttl_seconds=0)  # Persistent cache (never expire)
def search_news_finnhub(
    ticker: str,
    limit: int = 50,
    as_of: str | None = None,
    lookback_days: int = 7
) -> list[dict]:
    """Fetch company news from Finnhub with strict (from,to] window."""
```

**Key Features:**
- **Persistent caching**: `ttl_seconds=0` in decorator → cache never expires
- **Date windowing**: `as_of - lookback_days` to `as_of` (inclusive `to` date)
- **Rate limit handling**: 3 retries with exponential backoff on 429 errors
- **Heuristic sentiment**: `_heuristic_sentiment(title, summary)` generates tone proxy

**Sentiment Heuristic Logic:**
```python
positive_keywords = ["beats", "surge", "soar", "record", "upgrade", "strong", ...]
negative_keywords = ["miss", "slump", "plunge", "downgrade", "weak", "loss", ...]

# Score = (positive_count - negative_count) / 5.0, clamped to [-1, 1]
# Label = "Bullish" if > 0.15, "Bearish" if < -0.15, else "Neutral"
```

**Output Schema** (AlphaVantage-compatible for minimal downstream churn):
```python
{
    "title": str,
    "summary": str,
    "url": str,
    "source": str,
    "published": str,  # ISO-8601 UTC
    "overall_sentiment_score": float,  # Heuristic proxy
    "overall_sentiment_label": str,    # Bullish/Bearish/Neutral
    "ticker_sentiment_score": float,   # Same as overall (no ticker-specific breakdown)
    "ticker_sentiment_label": str,
    "relevance_score": 0.0,            # Placeholder (Finnhub doesn't provide)
}
```

### 2. News Harvester Agent (`backend/app/agents/analyst_team.py`)

**Unified Lookback Design:**
```python
UNIFIED_LOOKBACK_DAYS = 14  # Constant for all horizons

articles = search_news(
    ticker,
    limit=50,
    as_of=state.get('current_date'),
    lookback_days=UNIFIED_LOOKBACK_DAYS
)
```

**Why 14 days?**
- **Short horizon (k=10)**: Previously 7d; 14d captures earnings cycles better
- **Medium horizon (k=21)**: Was 14d; now unified
- **Long horizon (k=126)**: Was 30d; shorter window reduces noise and ensures 1-year historical compatibility
- **Reproducibility**: Fixed window across all ablations

**Provenance Block:**
```python
state['provenance']['news'] = {
    'ticker': 'AAPL',
    'as_of': '2025-03-03',
    'lookback_days': 14,
    'window_start': '2025-02-17',
    'window_end': '2025-03-03',
    'article_count': 23,
    'min_published': '2025-02-18T09:30:00+00:00',
    'max_published': '2025-03-03T14:22:00+00:00',
    'articles': [...]  # Top 10 articles with metadata
}
```

### 3. Environment Configuration

**.env Requirements:**
```bash
# Finnhub API key (support both spellings)
FINNHUB_API_KEY=your_key_here
# or
FINHUB_API_KEY=your_key_here
```

**Early Load** (`backend/app/__init__.py`):
```python
from dotenv import load_dotenv
load_dotenv()  # Ensures FINNHUB_API_KEY available before imports
```

### 4. Caching Infrastructure (`backend/app/utils/cache.py`)

**Persistent Cache Support:**
```python
def get(self, key: str) -> Any:
    """Retrieve cached value. ttl_seconds=0 means never expire."""
    if key in self.cache:
        value, timestamp = self.cache[key]
        if self.ttl_seconds == 0 or time.time() - timestamp < self.ttl_seconds:
            return value
        # Only expire if TTL > 0 and time elapsed
```

**Cache Key Generation:**
- MD5 hash of `(function_name, args, kwargs)` → deterministic across runs
- Includes `ticker`, `as_of`, `lookback_days` → each date/ticker cached independently

---

## Evaluation Window Constraints

### Historical Coverage
**Finnhub Free Tier**: ~1 year rolling historical news (exact window varies by company)

**Recommended Evaluation Dates for FYP (2026-02-12 baseline):**
```python
# Safe range: 2025-03 to 2026-02 (within trailing 12 months)
dates = [
    "2025-03-03", "2025-03-17", "2025-03-31",
    "2025-04-14", "2025-04-28",
    # ... through ...
    "2026-01-19", "2026-02-02"
]
```

**Why this range?**
- Stays comfortably inside Finnhub's 1-year window
- Bi-weekly cadence → ~25 dates for 5 tickers = 125 runs
- Allows 14-day lookback without hitting historical boundary

### Rate Limit Compliance
**60 calls/minute** = safe for sequential execution or `--workers=2`

**Typical Batch Run:**
- 5 tickers × 25 dates = 125 API calls
- With cache: ~10 calls (first run), 0 calls (subsequent runs due to persistent cache)
- Time: 125s first run, <1s cached runs

---

## Validation & Testing

### Quick Integration Test
```bash
cd nexustrader/backend
python test_social_media_integration.py
```

**Expected Output:**
```
[1/3] Testing Finnhub company news...
✅ SUCCESS: Retrieved 23 articles for TSLA
   Sample: Tesla reports record Q4 deliveries...
   Tone: Bullish 0.40
```

### End-to-End Batch Test
```bash
cd nexustrader/experiments/scripts
python run_batch.py \
  --tickers AAPL \
  --dates 2025-03-03 \
  --horizon short \
  --tag finnhub_test \
  --workers 1
```

**Check Provenance:**
```bash
cd nexustrader/experiments/results/raw
cat batch_finnhub_test_*.jsonl | jq '.result.provenance.news'
```

**Expected Fields:**
```json
{
  "ticker": "AAPL",
  "lookback_days": 14,
  "article_count": 23,
  "window_start": "2025-02-17",
  "window_end": "2025-03-03"
}
```

---

## Comparison: AlphaVantage vs Finnhub

| Feature | AlphaVantage (old) | Finnhub (new) |
|---------|-------------------|---------------|
| **Historical range** | 30+ years | 1 year (free) |
| **Rate limit** | 25/day (free) | 60/min (free) |
| **Native sentiment** | ✅ Per-ticker scores | ❌ Premium only |
| **Date filtering** | Time_from/to (specific format) | Standard YYYY-MM-DD |
| **Batch feasibility** | ❌ 25/day blocks 100+ runs | ✅ 60/min enables full scale |
| **Caching strategy** | 30-min TTL | Persistent (0 TTL) |
| **FYP viability** | ❌ | ✅ |

---

## Troubleshooting

### Issue: "No articles returned"
**Causes:**
1. Date range outside Finnhub's 1-year historical window
2. Invalid API key or rate limit exceeded
3. Ticker not covered (e.g., non-US or OTC stocks)

**Solutions:**
- Check `as_of - 14d` is within last ~360 days
- Verify `FINNHUB_API_KEY` in `.env`
- Test with major US tickers (AAPL, MSFT, NVDA)

### Issue: "Rate limit 429 errors"
**Cause:** >60 requests/minute

**Solution:**
- Use `--workers=1` or `--workers=2` (default is sequential)
- Persistent cache means 429 only occurs on first run; subsequent runs use cache

### Issue: "Cache not persisting across runs"
**Cause:** Cache is in-memory and clears on backend restart

**Expected Behavior:**
- Cache persists **within a single backend session**
- Restarting `uvicorn` clears cache (by design for development)
- Production: consider Redis or disk-backed cache for multi-day persistence

---

## Future Enhancements

### Potential Upgrades (if needed)
1. **Disk-backed cache** (e.g., `diskcache` library) for permanent persistence
2. **Premium Finnhub** for native sentiment scores (if heuristic insufficient)
3. **MarketAux integration** as secondary source (100 req/day, 3 articles/req, has sentiment)
4. **Entity-level sentiment** from MarketAux for multi-company analysis

### Current Trade-offs
- **Heuristic sentiment** vs native scores: 
  - Pro: Deterministic, no extra API cost
  - Con: Less nuanced than ML-based sentiment
  - Mitigation: LLM can infer tone from headlines/summaries during analysis
- **14-day unified window** vs horizon-specific:
  - Pro: Cleaner i.i.d. assumption, less confounding
  - Con: Long horizon (k=126) sees less recent context proportionally
  - Mitigation: Agent synthesis step can still use forward-looking horizon parameter

---

## Summary for FYP Report

**News Data Pipeline:**
1. **Source**: Finnhub Company News API (free tier, 1-year historical)
2. **Retrieval**: 14-day lookback window from simulation date
3. **Caching**: Persistent in-memory cache (never expires within session) for reproducibility
4. **Sentiment**: Deterministic keyword-based heuristic (Bullish/Neutral/Bearish labels + [-1,1] scores)
5. **Integration**: News harvester agent → LLM synthesis → trading strategy

**Design Rationale:**
- **Reproducibility**: Fixed cache + unified lookback → identical news inputs across ablations
- **Scalability**: 60/min rate limit + caching → 125 runs complete in ~2 min first pass, <1s cached
- **Cost**: $0 (free tier sufficient for FYP scale: 5 tickers × 25 dates = 125 unique ticker-date pairs)

**Validation:**
- Each run captures news provenance (article count, date range, titles) in output JSONL
- Integration test confirms >0 articles retrieved for major tickers within 2025-2026 window
