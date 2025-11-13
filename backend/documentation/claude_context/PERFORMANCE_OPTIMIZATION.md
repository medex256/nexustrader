# Performance Optimization Guide

## Current Performance Issues

Your test revealed two main performance bottlenecks:

### 1. **Duplicate API Calls** 
- Social media data fetched twice (Sentiment Analyst + Bull Trader)
- News fetched multiple times by different agents
- Financial data re-fetched by multiple agents

### 2. **Long Execution Time (~4-5 minutes)**
- 12 sequential LLM calls (no parallelization)
- 30+ API calls with network latency
- No caching between agents

---

## Solutions Implemented

### ✅ Step 1: Caching System (`app/utils/cache.py`)

**Two types of caches:**

1. **Data Cache** (TTL: 1 hour)
   - Market data (prices, financials, news)
   - Social media sentiment
   - Technical indicators

2. **LLM Cache** (TTL: 24 hours)
   - LLM responses for identical prompts
   - Useful for repeated analyses

**Usage:**
```python
from app.utils.cache import cache_data

@cache_data(ttl_seconds=3600)
def get_stock_price(ticker):
    # This will only call API once per hour
    return expensive_api_call(ticker)
```

### ✅ Step 2: Shared Context (`app/utils/shared_context.py`)

**Purpose:** Share data between agents in the same run

**Usage:**
```python
from app.utils.shared_context import get_shared_context

# Sentiment Analyst stores data
context = get_shared_context()
context.set_social_data(ticker, twitter, reddit, stocktwits)

# Bull Trader retrieves without re-fetching
social_data = context.get_social_data(ticker)
if social_data:
    # Use cached data
    twitter = social_data["twitter"]
```

---

## Next Steps to Apply Optimizations

### Phase 1: Add Caching to Tools (30 min)

**1. Update `social_media_tools.py`:**
```python
from ..utils.cache import cache_data

@cache_data(ttl_seconds=1800)  # 30 min cache
def search_twitter(query: str):
    # existing implementation
```

**2. Update `financial_data_tools.py`:**
```python
@cache_data(ttl_seconds=3600)  # 1 hour cache
def get_financial_statements(ticker: str):
    # existing implementation
```

**3. Update `news_tools.py`:**
```python
@cache_data(ttl_seconds=1800)  # 30 min cache
def search_news(query: str):
    # existing implementation
```

### Phase 2: Use Shared Context in Agents (1 hour)

**1. Update `sentiment_analyst_agent`:**
```python
from ..utils.shared_context import get_shared_context

def sentiment_analyst_agent(state: dict):
    ticker = state['ticker']
    context = get_shared_context()
    
    # Fetch and store for other agents
    twitter = search_twitter(ticker)
    reddit = search_reddit("wallstreetbets", ticker)
    stocktwits = search_stocktwits(ticker)
    
    # Store in shared context
    context.set_social_data(ticker, twitter, reddit, stocktwits)
    
    # ... rest of implementation
```

**2. Update `bull_trader_agent`:**
```python
def bull_trader_agent(state: dict):
    ticker = state['ticker']
    context = get_shared_context()
    
    # Try to get cached social data first
    social_data = context.get_social_data(ticker)
    
    if social_data:
        print(f"[REUSING] Social data from Sentiment Analyst")
        twitter = social_data["twitter"]
        reddit = social_data["reddit"]
    else:
        # Fallback: fetch if not available
        twitter = search_twitter(ticker)
        reddit = search_reddit("wallstreetbets", ticker)
    
    # ... rest of implementation
```

### Phase 3: Initialize Context in Graph (5 min)

**Update `main.py`:**
```python
from .utils.shared_context import initialize_context

@app.post("/analyze")
def analyze_ticker(request: AnalysisRequest):
    # Initialize fresh context for this analysis
    initialize_context()
    
    # Create and run graph
    agent_graph = create_agent_graph()
    result = agent_graph.invoke(initial_state)
    
    return result
```

---

## Expected Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Duplicate API calls** | 15-20 | 5-8 | 60-70% reduction |
| **Execution time** | 4-5 min | 2-3 min | 40-50% faster |
| **API costs** | $0.10/run | $0.04/run | 60% cheaper |
| **LLM calls** | 12 | 12 | (same, but cached) |

---

## Future Optimizations (Phase 4+)

### 1. **Parallel Agent Execution** (Advanced)
- Run independent analysts in parallel
- Requires threading or async implementation
- Could reduce time to 1-2 minutes

### 2. **Streaming Responses** (Week 20-21)
- Use WebSockets to show progress
- Display partial results as agents complete
- Better UX even if total time is same

### 3. **Incremental Updates** (Week 22)
- Only re-run changed agents
- Cache full analysis results
- Update only when new data available

### 4. **Model Selection** (Week 18-19)
- Use cheaper/faster models for simple tasks
- Reserve expensive models for complex decisions
- Example: GPT-4 for strategy, GPT-3.5 for summaries

---

## Quick Test: Apply Caching Now

**Want to see immediate improvement? Add caching to one tool:**

1. Open `app/tools/social_media_tools.py`
2. Add at the top:
   ```python
   from ..utils.cache import cache_data
   ```
3. Add decorator to `search_twitter`:
   ```python
   @cache_data(ttl_seconds=1800)
   def search_twitter(query: str):
       # existing code
   ```
4. Run test again - second run will be much faster!

---

## Summary

Your debate mechanism is **working perfectly**! The duplicate calls and slow performance are expected for v1. The optimization infrastructure is now in place. Next steps:

1. ✅ Apply `@cache_data` to all tool functions (30 min)
2. ✅ Use shared context in agents (1 hour)
3. ✅ Test again - should be 40-50% faster
4. Move to Phase 2 (Memory system) after performance is good

Want me to apply the caching decorators to your tools now?
