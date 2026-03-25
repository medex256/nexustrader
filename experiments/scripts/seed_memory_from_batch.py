"""
seed_memory_from_batch.py — Seed ChromaDB from a frozen B+ batch file.

This avoids re-running 385 analyses from scratch. It reads the B+ JSONL,
stores each analysis into ChromaDB (as if it had been a Stage D cold run),
computes the k-day forward return via yfinance, and immediately labels the
memory with CORRECT/WRONG + a template lesson.

No LLM calls are made during seeding. Lessons are template-generated
(factual: action, outcome, return). The memory is still useful — the
Upside/Downside analysts will see pattern + outcome, which is the signal.

Usage:
    # Dry run — preview without writing
    python scripts/seed_memory_from_batch.py --input results/raw/batch_eval385_stageB_plus_v3_20260318_162135.jsonl --dry-run

    # Seed for real (ChromaDB must already be empty — run reset_memory.py first)
    python scripts/seed_memory_from_batch.py --input results/raw/batch_eval385_stageB_plus_v3_20260318_162135.jsonl

    # With LLM-generated lessons instead of templates (costs 385 API calls)
    python scripts/seed_memory_from_batch.py --input ... --llm-lessons
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional, List, Tuple

import pandas as pd
import yfinance as yf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPERIMENTS_DIR = os.path.dirname(SCRIPT_DIR)
BACKEND_DIR = os.path.normpath(os.path.join(EXPERIMENTS_DIR, "..", "backend"))
sys.path.insert(0, BACKEND_DIR)

CHROMA_PATH = os.path.join(BACKEND_DIR, "chroma_db")
HOLD_EPSILON = 0.02  # matches scoring notebook (2% threshold for correct HOLD)

HORIZON_MAP = {"short": 10, "medium": 21, "long": 126}


# --------------------------------------------------------------------------- #
# Forward-return helpers (same as update_memory_outcomes.py)
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=256)
def _fetch_closes(ticker: str, start_str: str, end_str: str) -> Tuple[Optional[List[float]], Optional[str]]:
    try:
        hist = yf.Ticker(ticker).history(start=start_str, end=end_str)
        if hist.empty:
            return None, "empty_history"
        return hist["Close"].dropna().tolist(), None
    except Exception as e:
        print(f"  [yfinance ERROR] {ticker} {start_str}→{end_str}: {e}")
        return None, str(e)


def get_k_day_return(ticker: str, as_of: str, k: int) -> Optional[float]:
    start = datetime.fromisoformat(as_of)
    end = start + timedelta(days=max(14, k * 3))
    # Use YYYY-MM-DD strings — yfinance silently returns empty data on ISO datetime strings
    start_str = start.strftime('%Y-%m-%d')
    end_str = end.strftime('%Y-%m-%d')
    closes, err = _fetch_closes(ticker, start_str, end_str)
    if closes is None:
        return None
    if len(closes) <= k:
        return None
    entry, exit_price = float(closes[0]), float(closes[k])
    if entry == 0:
        return None
    return (exit_price - entry) / entry


def outcome_label(action: str, k_return: float) -> str:
    if action == "BUY":
        return "CORRECT" if k_return > 0 else "WRONG"
    elif action == "SELL":
        return "CORRECT" if k_return < 0 else "WRONG"
    else:  # HOLD
        return "CORRECT" if abs(k_return) < HOLD_EPSILON else "WRONG"


def template_lesson(ticker: str, simulated_date: str, action: str, outcome: str, k_return: float) -> str:
    direction = "rose" if k_return > 0 else "fell"
    return (
        f"{ticker} on {simulated_date}: {action} call was {outcome}. "
        f"Price {direction} {abs(k_return):.2%} over the evaluation horizon."
    )


def llm_lesson(ticker: str, simulated_date: str, action: str, outcome: str,
               k_return: float, reports: dict) -> str:
    try:
        from app.llm import invoke_llm
        direction = "rose" if k_return > 0 else "fell"
        fund = (reports.get("fundamental_analyst") or "")[:400]
        tech = (reports.get("technical_analyst") or "")[:400]
        prompt = (
            f"Stock: {ticker}  Date: {simulated_date}  Action: {action}  "
            f"Outcome: {outcome}  Actual k-day return: {k_return:+.2%} (price {direction})\n\n"
            f"Fundamental signal excerpt:\n{fund}\n\nTechnical signal excerpt:\n{tech}\n\n"
            "In 1-2 sentences, identify the single most important reason this call was "
            f"{'correct' if outcome == 'CORRECT' else 'incorrect'}. "
            "Be specific — no generic hedging."
        )
        return invoke_llm(prompt).strip()
    except Exception as e:
        print(f"  [LESSON] LLM call failed ({e}), using template.")
        return template_lesson(ticker, simulated_date, action, outcome, k_return)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(description="Seed ChromaDB memory from a frozen B+ batch JSONL.")
    parser.add_argument("--input", required=True, help="Path to B+ batch JSONL file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to ChromaDB")
    parser.add_argument("--llm-lessons", action="store_true",
                        help="Generate lessons via LLM (costs 1 API call per row). Default: template lessons.")
    parser.add_argument("--k", type=int, default=None, help="Force horizon k. If omitted, reads from JSONL.")
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

    # Filter out error rows
    rows = [r for r in rows if not r.get("error")]
    print(f"Loaded {len(rows)} valid rows from {os.path.basename(args.input)}")

    if not args.dry_run:
        from app.utils.memory import FinancialMemory
        memory = FinancialMemory(persist_directory=CHROMA_PATH)
        existing = memory.collection.count()
        if existing > 0:
            print(f"\nWARNING: ChromaDB already contains {existing} memories.")
            print("Run reset_memory.py --confirm first if you want a clean seed.")
            print("Continuing — will add on top of existing memories.\n")

    stored = skipped = errors = 0

    for row in rows:
        ticker = row.get("ticker")
        simulated_date = row.get("simulated_date")

        if not ticker or not simulated_date:
            skipped += 1
            continue

        # Support both trace JSONL (row["trace"]) and raw JSONL (row["result"])
        # Prefer trace — it has full reports + debate; raw only has action + rationale
        trace = row.get("trace") or {}
        result = row.get("result") or {}

        # Action: trace > result
        action = (
            (trace.get("trading_strategy") or {}).get("action")
            or (result.get("trading_strategy") or {}).get("action")
            or "HOLD"
        )

        # Resolve k
        if args.k:
            k = args.k
        else:
            horizon_str = row.get("horizon") or (trace.get("run_config") or {}).get("horizon", "short")
            k = HORIZON_MAP.get((horizon_str or "short").lower(), 10)

        # Compute forward return
        k_return = get_k_day_return(ticker, simulated_date, k)
        if k_return is None:
            print(f"  SKIP {ticker} {simulated_date}: could not fetch {k}-day return")
            skipped += 1
            continue

        outcome = outcome_label(action, k_return)
        pnl_pct = round(k_return * 100, 4)

        # Extract fields for storage — trace has full reports + debate; raw has only rationale
        reports = trace.get("reports") or {}
        debate_state = trace.get("investment_debate_state") or {}
        bull_args = debate_state.get("bull_history") or "N/A"
        bear_args = debate_state.get("bear_history") or "N/A"
        manager_decision = trace.get("investment_plan") or "N/A"
        strategy = trace.get("trading_strategy") or result.get("trading_strategy") or {"action": action}

        if not reports:
            print(f"  WARN {ticker} {simulated_date}: no reports found — using trace JSONL for best embeddings")

        # Generate lesson
        if args.llm_lessons:
            lesson = llm_lesson(ticker, simulated_date, action, outcome, k_return, reports)
        else:
            lesson = template_lesson(ticker, simulated_date, action, outcome, k_return)

        print(f"  {ticker} {simulated_date} | {action} | k={k} | return={k_return:+.2%} | {outcome}")
        if args.llm_lessons:
            print(f"    Lesson: {lesson}")

        if not args.dry_run:
            try:
                mem_id = memory.store_analysis(
                    ticker=ticker,
                    analysis_summary=f"Seeded from B+ batch: {ticker} {simulated_date}",
                    bull_arguments=bull_args,
                    bear_arguments=bear_args,
                    final_decision=manager_decision,
                    strategy=strategy,
                    metadata={
                        "simulated_date": simulated_date,
                        "market": row.get("market", "US"),
                        "horizon": row.get("horizon", "short"),
                        "source": "seeded_from_bplus",
                    },
                    reports=reports,
                )
                memory.update_outcome(
                    memory_id=mem_id,
                    actual_outcome=outcome,
                    profit_loss_pct=pnl_pct,
                    lessons_learned=lesson,
                )
                stored += 1
            except Exception as e:
                print(f"    ERROR: {e}")
                errors += 1
        else:
            stored += 1

    print(f"\nDone. Stored={stored}  Skipped={skipped}  Errors={errors}")
    if args.dry_run:
        print("(dry-run — nothing written to ChromaDB)")
    else:
        print(f"ChromaDB now contains {memory.collection.count()} memories.")


if __name__ == "__main__":
    main()
