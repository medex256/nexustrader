"""
update_memory_outcomes.py — Stage D post-run outcome updater.

After a Stage D batch run completes, this script:
1. Loads the JSONL batch file
2. Computes k-day forward return for each row via yfinance
3. Determines CORRECT / WRONG for each memory_id
4. Generates a lessons_learned string via a brief LLM call
5. Updates ChromaDB via memory.update_outcome()

Usage:
    python scripts/update_memory_outcomes.py --input results/raw/batch_stageD_<tag>.jsonl

The backend server does NOT need to be running. This script imports backend packages directly.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional, Tuple, List

import pandas as pd
import yfinance as yf

# Allow importing from the backend package
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPERIMENTS_DIR = os.path.dirname(SCRIPT_DIR)
BACKEND_DIR = os.path.join(os.path.dirname(EXPERIMENTS_DIR), "nexustrader", "backend")
# Handle both layouts: workspace/nexustrader/experiments and workspace/nexustrader/backend
for candidate in [
    os.path.join(EXPERIMENTS_DIR, "..", "backend"),
    os.path.join(EXPERIMENTS_DIR, "..", "..", "nexustrader", "backend"),
]:
    candidate = os.path.normpath(candidate)
    if os.path.isdir(candidate):
        sys.path.insert(0, candidate)
        break

HOLD_EPSILON = 0.02  # matches scoring notebook

HORIZON_MAP = {
    "short": 10,
    "medium": 21,
    "long": 126,
}


# --------------------------------------------------------------------------- #
# Forward-return helpers (same logic as score_results.py)
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=256)
def _fetch_closes(ticker: str, start_str: str, end_str: str) -> Tuple[Optional[List[float]], Optional[str]]:
    try:
        hist = yf.Ticker(ticker).history(start=start_str, end=end_str)
        if hist.empty:
            return None, "empty_history"
        return hist["Close"].dropna().tolist(), None
    except Exception as e:
        return None, str(e)


def get_k_day_return(ticker: str, as_of: str, k: int) -> Optional[float]:
    start = datetime.fromisoformat(as_of)
    end = start + timedelta(days=max(14, k * 3))
    closes, err = _fetch_closes(ticker, as_of, end.isoformat())
    if closes is None or len(closes) <= k:
        return None
    entry, exit_price = float(closes[0]), float(closes[k])
    if entry == 0:
        return None
    return (exit_price - entry) / entry


# --------------------------------------------------------------------------- #
# LLM lesson generator
# --------------------------------------------------------------------------- #

def generate_lesson(ticker: str, simulated_date: str, action: str,
                    correct: bool, k_return: float, reports: dict) -> str:
    """Call the backend LLM to produce a concise lessons_learned string."""
    try:
        from app.llm import invoke_llm
        direction = "rose" if k_return > 0 else "fell"
        outcome_str = "CORRECT" if correct else "WRONG"
        fund = (reports.get("fundamental_analyst", "") or "")[:400]
        tech = (reports.get("technical_analyst", "") or "")[:400]
        prompt = (
            f"Stock: {ticker}  Date: {simulated_date}  Action: {action}  "
            f"Outcome: {outcome_str}  Actual k-day return: {k_return:+.2%} (price {direction})\n\n"
            f"Fundamental signal excerpt:\n{fund}\n\nTechnical signal excerpt:\n{tech}\n\n"
            "In 1-2 sentences, identify the single most important reason this call was "
            f"{'correct' if correct else 'incorrect'}. Focus on what the signals indicated "
            "vs what happened. Be specific — no generic hedging."
        )
        return invoke_llm(prompt).strip()
    except Exception as e:
        print(f"  [LESSON] LLM call failed: {e}")
        direction = "rose" if k_return > 0 else "fell"
        return (
            f"Action was {action}; price {direction} {abs(k_return):.2%} over the horizon. "
            f"Outcome: {'CORRECT' if correct else 'WRONG'}."
        )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(description="Update ChromaDB memory outcomes from a Stage D JSONL batch file.")
    parser.add_argument("--input", required=True, help="Path to Stage D batch JSONL file")
    parser.add_argument("--k", type=int, default=None, help="Force horizon k (trading days). If omitted, reads from JSONL.")
    parser.add_argument("--dry-run", action="store_true", help="Print updates without writing to ChromaDB")
    args = parser.parse_args()

    if not os.path.isabs(args.input):
        args.input = os.path.join(EXPERIMENTS_DIR, args.input)

    if not os.path.exists(args.input):
        print(f"ERROR: File not found: {args.input}")
        sys.exit(1)

    # Load JSONL
    rows = []
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    print(f"Loaded {len(rows)} rows from {os.path.basename(args.input)}")

    # Filter rows that have a memory_id
    updateable = [r for r in rows if r.get("trace", {}).get("memory_id") or
                  r.get("response_full", {}).get("memory_id")]
    print(f"  {len(updateable)} rows have a memory_id")

    if not updateable:
        print("Nothing to update — no memory_ids found. Did you run Stage D with memory_on=True?")
        sys.exit(0)

    # Initialise memory
    if not args.dry_run:
        try:
            from app.utils.memory import FinancialMemory
            chroma_path = os.path.join(BACKEND_DIR, "chroma_db")
            memory = FinancialMemory(persist_directory=chroma_path)
        except Exception as e:
            print(f"ERROR: Could not initialise FinancialMemory: {e}")
            sys.exit(1)

    updated = skipped = errors = 0

    for row in updateable:
        ticker = row.get("ticker") or row.get("request", {}).get("ticker")
        simulated_date = row.get("simulated_date") or row.get("request", {}).get("simulated_date")
        action = (row.get("result_summary") or {}).get("action", "HOLD")

        # Resolve memory_id
        memory_id = (row.get("response_full") or {}).get("memory_id") or \
                    (row.get("trace") or {}).get("memory_id")

        # Resolve k
        if args.k:
            k = args.k
        else:
            horizon_str = row.get("horizon") or (row.get("request") or {}).get("horizon", "short")
            k = HORIZON_MAP.get(horizon_str.lower(), 10)

        if not all([ticker, simulated_date, memory_id]):
            print(f"  SKIP: missing ticker/date/memory_id — {row.get('ticker')} {row.get('simulated_date')}")
            skipped += 1
            continue

        # Compute forward return
        k_return = get_k_day_return(ticker, simulated_date, k)
        if k_return is None:
            print(f"  SKIP {ticker} {simulated_date}: could not fetch {k}-day return")
            skipped += 1
            continue

        # Determine outcome
        if action == "BUY":
            correct = k_return > 0
        elif action == "SELL":
            correct = k_return < 0
        else:  # HOLD
            correct = abs(k_return) < HOLD_EPSILON

        outcome_label = "CORRECT" if correct else "WRONG"
        pnl_pct = round(k_return * 100, 4)

        # Generate lesson
        reports = (row.get("response_full") or {}).get("reports", {})
        lesson = generate_lesson(ticker, simulated_date, action, correct, k_return, reports)

        print(f"  {ticker} {simulated_date} | {action} | k_return={k_return:+.2%} | {outcome_label} | memory_id={memory_id}")
        print(f"    Lesson: {lesson}")

        if not args.dry_run:
            try:
                memory.update_outcome(
                    memory_id=memory_id,
                    actual_outcome=outcome_label,
                    profit_loss_pct=pnl_pct,
                    lessons_learned=lesson,
                )
                updated += 1
            except Exception as e:
                print(f"    ERROR updating {memory_id}: {e}")
                errors += 1
        else:
            updated += 1

    print(f"\nDone. Updated={updated}  Skipped={skipped}  Errors={errors}")
    if args.dry_run:
        print("(dry-run — no changes written to ChromaDB)")


if __name__ == "__main__":
    main()
