#!/usr/bin/env python3
"""
Alpha Vantage Fundamentals Freezer — Pre-fetch and cache fundamental data.

Usage:
    python freeze_fundamentals.py                          # All tickers
    python freeze_fundamentals.py --tickers AAPL NVDA      # Specific tickers
    python freeze_fundamentals.py --dry-run                 # Show plan without fetching

Rate Limits (Alpha Vantage free tier):
    - 25 requests/day per key, 5 requests/minute
    - 3 endpoints × 5 tickers = 15 requests (easily done in one run)

What it fetches for each ticker:
    - INCOME_STATEMENT (annual + quarterly)
    - BALANCE_SHEET (annual + quarterly)
    - CASH_FLOW (annual + quarterly)

Output:
    experiments/cache/fundamentals/{ticker}/income_statement.json
    experiments/cache/fundamentals/{ticker}/balance_sheet.json
    experiments/cache/fundamentals/{ticker}/cash_flow.json

Each file contains ALL historical data (15+ years).
At runtime, filter by fiscalDateEnding <= simulated_date.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
EXPERIMENTS_DIR = SCRIPT_DIR.parent
INPUTS_DIR = EXPERIMENTS_DIR / "inputs"
CACHE_DIR = EXPERIMENTS_DIR / "cache" / "fundamentals"
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
INTER_CALL_DELAY = 13  # seconds between calls (safe for 5/min rate limit)

# The three fundamental endpoints we care about
ENDPOINTS = ["INCOME_STATEMENT", "BALANCE_SHEET", "CASH_FLOW"]


def fetch_av_fundamentals(ticker: str, function: str, api_key: str) -> tuple[dict | None, bool]:
    """
    Fetch Alpha Vantage fundamental data for a ticker.
    
    Args:
        ticker: Stock ticker symbol
        function: One of INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW
        api_key: Alpha Vantage API key
    
    Returns:
        (data, is_rate_limited): Full response dict or None, and whether key hit rate limit
    """
    params = {
        "function": function,
        "symbol": ticker,
        "apikey": api_key,
    }
    
    try:
        resp = requests.get(AV_BASE_URL, params=params, timeout=30)
        data = resp.json()
        
        # Rate limited - try next key
        if "Note" in data or "Information" in data:
            return None, True
        
        # Other errors - skip this pair
        if "Error Message" in data:
            print(f"    ⚠️  API Error: {data.get('Error Message', 'Unknown')}")
            return None, False
        
        # Success
        return data, False
    
    except Exception as e:
        print(f"    ❌ Exception: {e}")
        return None, False


def get_cache_path(ticker: str, function: str) -> Path:
    """Get the path for a frozen fundamental file."""
    filename = function.lower() + ".json"
    return CACHE_DIR / ticker.upper() / filename


def is_cached(ticker: str, function: str) -> bool:
    """Check if fundamental data is already frozen for this ticker/function."""
    return get_cache_path(ticker, function).exists()


def save_cache(ticker: str, function: str, data: dict):
    """Save fetched fundamental data to disk."""
    path = get_cache_path(ticker, function)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Add metadata
    output = {
        "ticker": ticker,
        "function": function,
        "fetched_at": datetime.now().isoformat(),
        "source": "alpha_vantage",
        "data": data,
    }
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def load_tickers(tickers_file: Path) -> list[str]:
    """Load tickers from a text file (one per line)."""
    with open(tickers_file, "r") as f:
        return [line.strip().upper() for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="Freeze Alpha Vantage fundamentals")
    parser.add_argument("--tickers", nargs="+", default=None, help="Tickers to fetch (default: from tickers.txt)")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without fetching")
    args = parser.parse_args()
    
    # Load tickers
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers_file = INPUTS_DIR / "tickers.txt"
        if not tickers_file.exists():
            print(f"❌ Tickers file not found: {tickers_file}")
            sys.exit(1)
        tickers = load_tickers(tickers_file)
    
    # Check API keys
    if not AV_KEYS:
        print("❌ No Alpha Vantage API keys found in .env")
        sys.exit(1)
    
    # Build work queue (ticker, function) pairs
    work = []
    for ticker in tickers:
        for function in ENDPOINTS:
            if not is_cached(ticker, function):
                work.append((ticker, function))
    
    cached_count = len(tickers) * len(ENDPOINTS) - len(work)
    total_calls = len(work)
    
    # Print summary
    print("=" * 60)
    print("  ALPHA VANTAGE FUNDAMENTALS FREEZER")
    print("=" * 60)
    print(f"  Tickers:         {tickers}")
    print(f"  Endpoints:       {ENDPOINTS}")
    print(f"  API Keys:        {len(AV_KEYS)} keys")
    print(f"  Total pairs:     {len(tickers) * len(ENDPOINTS)}")
    print(f"  Already cached:  {cached_count}")
    print(f"  To fetch:        {total_calls}")
    print(f"  Estimated time:  {total_calls * INTER_CALL_DELAY / 60:.1f} minutes")
    print("=" * 60)
    
    if total_calls == 0:
        print("\n✅ All fundamentals already cached!")
        return
    
    if args.dry_run:
        print("\n📋 DRY RUN - Would fetch:")
        for ticker, function in work[:10]:
            print(f"    {ticker:6s} {function}")
        if len(work) > 10:
            print(f"    ... and {len(work) - 10} more")
        return
    
    # Confirm before proceeding
    if not args.dry_run:
        print(f"\n⚠️  About to make {total_calls} API calls (~{total_calls * INTER_CALL_DELAY / 60:.1f} min)")
        response = input("Continue? [y/N]: ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    # Execute
    print("\n🚀 Starting fetch...")
    print("=" * 60)
    
    key_idx = 0
    success_count = 0
    skip_count = 0
    
    for i, (ticker, function) in enumerate(work, 1):
        print(f"[{i}/{total_calls}] {ticker:6s} {function}...", end=" ", flush=True)
        
        # Try each key until one works
        fetched = False
        for attempt in range(len(AV_KEYS)):
            api_key = AV_KEYS[key_idx]
            data, rate_limited = fetch_av_fundamentals(ticker, function, api_key)
            
            if rate_limited:
                print(f"⏳ Key {key_idx + 1} rate limited, trying next...", end=" ", flush=True)
                key_idx = (key_idx + 1) % len(AV_KEYS)
                continue
            
            if data is None:
                print("❌ Failed")
                skip_count += 1
                fetched = False
                break
            
            # Success
            save_cache(ticker, function, data)
            annual_count = len(data.get("annualReports", []))
            quarterly_count = len(data.get("quarterlyReports", []))
            print(f"✅ {annual_count} annual, {quarterly_count} quarterly")
            success_count += 1
            fetched = True
            break
        
        if fetched and i < total_calls:
            # Sleep between calls (except after last one)
            time.sleep(INTER_CALL_DELAY)
    
    # Summary
    print("=" * 60)
    print(f"✅ Complete: {success_count} fetched, {skip_count} failed, {cached_count} already cached")
    print(f"📂 Cache location: {CACHE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
