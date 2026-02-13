import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPERIMENTS_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_OUT_DIR = os.path.join(EXPERIMENTS_DIR, "results", "scored")

# Horizon mapping (must match backend)
HORIZON_MAP = {
    "short": 10,
    "medium": 21,
    "long": 126,
}


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def parse_date(date_str: str) -> datetime:
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return datetime.fromisoformat(date_str.split("T")[0])


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Warning: Skipping malformed JSON on line {line_no}: {path}", file=sys.stderr)
    return rows


@lru_cache(maxsize=256)
def fetch_ticker_history_cached(ticker: str, start_str: str, end_str: str) -> Tuple[Optional[List[float]], Optional[str]]:
    """
    Cached ticker history fetch. Returns (closes_list, error_msg).
    Cache key is (ticker, start_str, end_str) so identical requests reuse data.
    """
    try:
        start = parse_date(start_str)
        end = parse_date(end_str)
        hist = yf.Ticker(ticker).history(start=start, end=end)
        if hist.empty:
            return None, "empty_history"
        closes = hist["Close"].dropna().tolist()
        return closes, None
    except Exception as e:
        return None, str(e)


def get_k_day_return(ticker: str, as_of: str, k: int) -> Optional[float]:
    """
    Fetch k-day forward return. Now uses cached history fetcher.
    """
    start = parse_date(as_of)
    end = start + timedelta(days=max(14, k * 3))
    
    closes, err = fetch_ticker_history_cached(ticker, as_of, end.isoformat())
    if closes is None or len(closes) <= k:
        return None
    
    entry = float(closes[0])
    exit_price = float(closes[k])
    
    if entry == 0:
        return None
    
    return (exit_price - entry) / entry


def prefetch_all_histories(records: List[Tuple[str, str, int]], max_workers: int = 8) -> None:
    """
    Pre-fetch all unique (ticker, start, end) combinations in parallel.
    Populates the LRU cache before scoring loop.
    """
    unique_fetches = set()
    for ticker, as_of, k in records:
        start = parse_date(as_of)
        end = start + timedelta(days=max(14, k * 3))
        unique_fetches.add((ticker, as_of, end.isoformat()))
    
    print(f"Pre-fetching {len(unique_fetches)} unique ticker histories (parallel, max_workers={max_workers})...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_ticker_history_cached, t, s, e): (t, s, e)
            for t, s, e in unique_fetches
        }
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            if completed % 10 == 0 or completed == len(futures):
                print(f"  Fetched {completed}/{len(futures)}", end="\r")
        print()  # newline after progress
    
    print("✅ Pre-fetch complete. All requests will now hit cache.")



def score_action(action: str, k_return: Optional[float], hold_mode: str, epsilon: float) -> Optional[int]:
    if k_return is None:
        return None

    action = (action or "HOLD").upper()
    if action == "HOLD":
        if hold_mode == "zero":
            return 0
        if hold_mode == "exclude":
            return None
        if hold_mode == "neutral-band":
            # HOLD is considered correct if the magnitude of the move is small.
            # Example: epsilon=0.01 means HOLD is correct when |return| < 1%.
            return 1 if abs(float(k_return)) < float(epsilon) else 0

    if action == "BUY":
        return 1 if k_return > 0 else 0
    if action == "SELL":
        return 1 if k_return < 0 else 0

    return None


def extract_action(record: Dict[str, Any]) -> str:
    result = record.get("result", {})
    strategy = result.get("trading_strategy", {}) if isinstance(result, dict) else {}
    return strategy.get("action", "HOLD")


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    summary = []
    for action, group in df.groupby("action"):
        valid = group.dropna(subset=["score"])
        total = len(valid)
        acc = (valid["score"].sum() / total) if total > 0 else 0
        summary.append({
            "action": action,
            "count": len(group),
            "scored": total,
            "accuracy": round(acc, 4),
            "avg_return": round(valid["k_return"].mean(), 6) if total > 0 else None,
        })

    overall = df.dropna(subset=["score"])
    overall_acc = (overall["score"].sum() / len(overall)) if len(overall) > 0 else 0
    summary.append({
        "action": "ALL",
        "count": len(df),
        "scored": len(overall),
        "accuracy": round(overall_acc, 4),
        "avg_return": round(overall["k_return"].mean(), 6) if len(overall) > 0 else None,
    })

    return pd.DataFrame(summary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score NexusTrader batch outputs.")
    parser.add_argument("--input", required=True, help="Path to batch JSONL output")
    parser.add_argument("--k", type=int, default=None, help="Forward horizon in trading days (overrides JSONL horizon if set)")
    parser.add_argument(
        "--hold",
        choices=["exclude", "zero", "neutral-band"],
        default="exclude",
        help="How to score HOLD (neutral-band: HOLD is correct if |return| < epsilon)",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=0.01,
        help="Neutral band for HOLD when --hold neutral-band (e.g., 0.01 = 1%)",
    )
    parser.add_argument("--out", default=DEFAULT_OUT_DIR, help="Output directory")
    parser.add_argument("--tag", default="score", help="Tag to include in output filename")

    args = parser.parse_args()

    rows = load_jsonl(args.input)
    if not rows:
        print("No rows found in input.")
        return 1

    ensure_dir(args.out)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Step 1: Collect all (ticker, as_of, k) tuples
    fetch_list = []
    for row in rows:
        ticker = row.get("ticker")
        simulated_date = row.get("simulated_date")
        horizon_str = row.get("horizon", "short")
        
        if not ticker or not simulated_date:
            continue
        
        if args.k is not None:
            k = args.k
        else:
            k = HORIZON_MAP.get(horizon_str.lower(), 10)
        
        fetch_list.append((ticker, simulated_date, k))
    
    # Step 2: Pre-fetch all histories in parallel (populates cache)
    prefetch_all_histories(fetch_list, max_workers=8)
    
    # Step 3: Score all rows (now hitting cache, very fast)
    print("Scoring runs...")
    records = []
    for row in rows:
        ticker = row.get("ticker")
        simulated_date = row.get("simulated_date")
        horizon_str = row.get("horizon", "short")
        action = extract_action(row)

        if not ticker or not simulated_date:
            continue

        # Determine k: use CLI override if provided, else resolve from horizon
        if args.k is not None:
            k = args.k
        else:
            k = HORIZON_MAP.get(horizon_str.lower(), 10)

        k_return = get_k_day_return(ticker, simulated_date, k)
        score = score_action(action, k_return, args.hold, args.epsilon)

        records.append({
            "ticker": ticker,
            "simulated_date": simulated_date,
            "horizon": horizon_str,
            "k": k,
            "action": action,
            "k_return": k_return,
            "score": score,
        })

    df = pd.DataFrame(records)
    detail_path = os.path.join(args.out, f"scores_{args.tag}_{timestamp}.csv")
    df.to_csv(detail_path, index=False)

    summary_df = summarize(df)
    summary_path = os.path.join(args.out, f"summary_{args.tag}_{timestamp}.csv")
    summary_df.to_csv(summary_path, index=False)

    print(f"Scoring complete. Detail: {detail_path}")
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
