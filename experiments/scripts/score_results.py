import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

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


def get_k_day_return(ticker: str, as_of: str, k: int) -> Optional[float]:
    start = parse_date(as_of)
    end = start + timedelta(days=max(14, k * 3))

    hist = yf.Ticker(ticker).history(start=start, end=end)
    if hist.empty or len(hist) <= k:
        return None

    closes = hist["Close"].dropna().tolist()
    if len(closes) <= k:
        return None

    entry = float(closes[0])
    exit_price = float(closes[k])

    if entry == 0:
        return None

    return (exit_price - entry) / entry


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
