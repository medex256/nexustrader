#!/usr/bin/env python3
"""
Alpha Vantage News Freezer — Pre-fetch and cache news for all tickers × dates.

Usage:
    python freeze_news.py                          # Default: all tickers × expanded dates
    python freeze_news.py --tickers AAPL NVDA      # Specific tickers
    python freeze_news.py --dates-file dates.txt   # Custom dates file
    python freeze_news.py --dry-run                 # Show plan without fetching

Rate Limits (Alpha Vantage free tier):
    - 25 requests/day per key, 5 requests/minute
    - With 2 keys: ~50 requests/day
    - 5 tickers × 76 dates = 380 fetches → ~8 days

The script is RESUMABLE: it skips any (ticker, date) that already has a frozen file.
Run it daily until complete — it picks up where it left off.

Output:
    experiments/cache/news/{ticker}/{date}.json
    Each file contains the Alpha Vantage NEWS_SENTIMENT response (list of articles).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
EXPERIMENTS_DIR = SCRIPT_DIR.parent
INPUTS_DIR = EXPERIMENTS_DIR / "inputs"
CACHE_DIR = EXPERIMENTS_DIR / "cache" / "news"
BACKEND_DIR = EXPERIMENTS_DIR.parent / "backend"

# Load .env from backend
load_dotenv(BACKEND_DIR / ".env")

# ── Alpha Vantage Config ──────────────────────────────────────────────
AV_KEYS = [
    k for k in [
        os.getenv("ALPHA_VANTAGE_SENTIMENT_KEY"),
        os.getenv("ALPHA_VANTAGE_API_KEY_SECOND"),
        os.getenv("ALPHA_THIRD"),
        os.getenv("ALPHA_FOURTH"),
        os.getenv("ALPHA_FIFTH"),
        os.getenv("ALPHA_SIXTH"),
    ] if k
]

AV_BASE_URL = "https://www.alphavantage.co/query"
LOOKBACK_DAYS = 14
CALLS_PER_DAY_PER_KEY = 25
INTER_CALL_DELAY = 13  # seconds between calls (safe for 5/min rate limit)


def fetch_av_news(ticker: str, date_str: str, api_key: str) -> tuple[list[dict], bool]:
    """
    Fetch Alpha Vantage NEWS_SENTIMENT for a ticker.
    
    Returns:
        (articles, is_rate_limited): list of articles and whether the key hit rate limit
    """
    end_dt = datetime.fromisoformat(date_str)
    start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
    
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": ticker,
        "time_from": start_dt.strftime("%Y%m%dT0000"),
        "time_to": end_dt.strftime("%Y%m%dT2359"),
        "limit": 50,
        "sort": "RELEVANCE",
        "apikey": api_key,
    }
    
    try:
        resp = requests.get(AV_BASE_URL, params=params, timeout=30)
        data = resp.json()
        
        # Rate limited - try next key
        if "Note" in data or "Information" in data:
            return [], True
        
        # Other errors - skip this pair
        if "Error Message" in data:
            return [], False
        
        # Success - convert to our schema
        articles = []
        for item in data.get("feed", []):
            ticker_sentiment = next(
                (ts for ts in item.get("ticker_sentiment", []) 
                 if ts.get("ticker", "").upper() == ticker.upper()),
                {}
            )
            
            articles.append({
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "url": item.get("url", ""),
                "source": item.get("source", "Unknown"),
                "published": item.get("time_published", ""),
                "overall_sentiment_score": float(item.get("overall_sentiment_score", 0)),
                "overall_sentiment_label": item.get("overall_sentiment_label", "Neutral"),
                "ticker_sentiment_score": float(ticker_sentiment.get("ticker_sentiment_score", 0)),
                "ticker_sentiment_label": ticker_sentiment.get("ticker_sentiment_label", "Neutral"),
                "relevance_score": float(ticker_sentiment.get("relevance_score", 0)),
            })
        
        return articles, False
    
    except Exception as e:
        print(f"Error: {e}")
        return [], False


def get_cache_path(ticker: str, date_str: str) -> Path:
    """Get the path for a frozen news file."""
    return CACHE_DIR / ticker.upper() / f"{date_str}.json"


def is_cached(ticker: str, date_str: str) -> bool:
    """Check if news is already frozen for this ticker/date."""
    return get_cache_path(ticker, date_str).exists()


def save_cache(ticker: str, date_str: str, articles: list[dict]):
    """Save fetched articles to disk."""
    path = get_cache_path(ticker, date_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "ticker": ticker,
            "date": date_str,
            "lookback_days": LOOKBACK_DAYS,
            "fetched_at": datetime.now().isoformat(),
            "source": "alpha_vantage",
            "article_count": len(articles),
            "articles": articles,
        }, f, indent=2, ensure_ascii=False)


def load_dates(dates_file: Path) -> list[str]:
    """Load dates from a text file (one per line)."""
    with open(dates_file, "r") as f:
        return [line.strip() for line in f if line.strip()]


def load_tickers(tickers_file: Path) -> list[str]:
    """Load tickers from a text file (one per line)."""
    with open(tickers_file, "r") as f:
        return [line.strip() for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="Freeze Alpha Vantage news for experiment dates")
    parser.add_argument("--tickers", nargs="+", default=None, help="Tickers to fetch (default: from tickers.txt)")
    parser.add_argument("--dates-file", type=str, default=None, help="Dates file (default: dates_expanded.txt)")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without fetching")
    parser.add_argument("--max-calls", type=int, default=None, help="Max API calls this run (default: auto from key count)")
    args = parser.parse_args()
    
    # Load tickers
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers = load_tickers(INPUTS_DIR / "tickers.txt")
    
    # Load dates
    dates_file = Path(args.dates_file) if args.dates_file else INPUTS_DIR / "dates_expanded.txt"
    dates = load_dates(dates_file)
    
    # Check API keys
    if not AV_KEYS:
        print("❌ No Alpha Vantage API keys found in .env")
        sys.exit(1)
    
    # Build work queue
    work = []
    for ticker in tickers:
        for date_str in dates:
            if not is_cached(ticker, date_str):
                work.append((ticker, date_str))
    
    cached = len(tickers) * len(dates) - len(work)
    max_calls = args.max_calls or (CALLS_PER_DAY_PER_KEY * len(AV_KEYS))
    
    # Print summary
    print("=" * 60)
    print("  ALPHA VANTAGE NEWS FREEZER")
    print("=" * 60)
    print(f"  Tickers:         {tickers}")
    print(f"  Dates:           {len(dates)} ({dates[0]} → {dates[-1]})")
    print(f"  Already cached:  {cached}")
    print(f"  Remaining:       {len(work)}")
    print(f"  API keys:        {len(AV_KEYS)}")
    print(f"  Max calls/run:   {min(len(work), max_calls)}")
    print("=" * 60)
    
    if not work:
        print("\n✅ All news already frozen!")
        return
    
    if args.dry_run:
        print(f"\n🔍 DRY RUN — showing first 20 of {len(work)} pending:")
        for ticker, date_str in work[:20]:
            print(f"    {ticker} / {date_str}")
        return
    
    # Fetch loop
    print(f"\n🚀 Fetching (13s delay between calls)...\n")
    
    rate_limited_keys = set()
    calls_made = 0
    success = 0
    
    for ticker, date_str in work:
        if calls_made >= max_calls:
            break

        # Try keys until one provides articles, or all are exhausted
        final_articles = None
        any_valid_response = False
        tried_keys_count = 0
        newly_rate_limited_count = 0

        for key_idx, api_key in enumerate(AV_KEYS):
            if api_key in rate_limited_keys:
                continue

            tried_keys_count += 1
            # Use the same call count for retries on the same work item for display
            print(f"  [{calls_made + 1}] {ticker}/{date_str} (key {key_idx + 1})...", end=" ")
            articles, is_rate_limited = fetch_av_news(ticker, date_str, api_key)

            if is_rate_limited:
                print("⏸️  rate limited")
                rate_limited_keys.add(api_key)
                newly_rate_limited_count += 1
                continue

            # Got a valid response that isn't a rate-limit error
            any_valid_response = True
            final_articles = articles

            if articles:  # Non-empty list, we are done with this item
                break
            else:  # Empty list, try the next key
                print("-> 0 articles, trying next key...")

        # After trying all keys for a ticker/date, decide what to do
        if any_valid_response:
            save_cache(ticker, date_str, final_articles)
            if final_articles:
                print(f"✅ {len(final_articles)} articles")
            else:
                # This line is reached if all valid keys returned 0 articles
                valid_key_attempts = tried_keys_count - newly_rate_limited_count
                summary = f"all {valid_key_attempts} valid keys returned 0"
                if newly_rate_limited_count > 0:
                    summary += f"; {newly_rate_limited_count} keys hit rate-limit"
                print(f"✅ 0 articles ({summary})")

            calls_made += 1
            success += 1

            # Delay before next call
            if calls_made < max_calls and calls_made < len(work):
                time.sleep(INTER_CALL_DELAY)
        else:
            # All keys were either in rate_limited_keys or became rate-limited
            summary = f"{newly_rate_limited_count} newly rate-limited"
            if tried_keys_count == newly_rate_limited_count and tried_keys_count > 0:
                summary = f"all {tried_keys_count} tried keys were rate-limited"
            
            print(f"  ❌ All keys exhausted for {ticker}/{date_str} ({summary})")
            break
    
    # Summary
    remaining = len(work) - success
    print(f"\n{'=' * 60}")
    print(f"  Fetched:   {success}")
    print(f"  Remaining: {remaining}")
    if remaining > 0:
        print(f"  Run again tomorrow! (~{remaining / max_calls:.1f} more days)")
    else:
        print(f"  🎉 Complete!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
