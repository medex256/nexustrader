import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Any, Literal, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPERIMENTS_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_TICKERS_FILE = os.path.join(EXPERIMENTS_DIR, "inputs", "tickers.txt")
DEFAULT_DATES_FILE = os.path.join(EXPERIMENTS_DIR, "inputs", "dates.txt")
DEFAULT_OUT_DIR = os.path.join(EXPERIMENTS_DIR, "results", "raw")


def parse_list(arg: str) -> List[str]:
    if not arg:
        return []
    return [item.strip() for item in arg.split(",") if item.strip()]


def load_list_from_file(path: str) -> List[str]:
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _safe_get(dct: Any, *path: str, default: Any = None) -> Any:
    cur = dct
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def _truncate_text(value: Any, max_chars: int) -> Any:
    if max_chars <= 0:
        return value
    if isinstance(value, str) and len(value) > max_chars:
        return value[:max_chars] + "…"
    return value


def compact_result(full: Dict[str, Any], truncate_chars: int = 400) -> Dict[str, Any]:
    trading_strategy = _safe_get(full, "trading_strategy", default={})
    proposed_trade = _safe_get(full, "proposed_trade", default={})
    risk_gate = _safe_get(full, "risk_reports", "risk_gate")

    # Trim long text fields (LLM tends to generate very large blobs)
    if isinstance(trading_strategy, dict) and "rationale" in trading_strategy:
        trading_strategy = dict(trading_strategy)
        trading_strategy["rationale"] = _truncate_text(trading_strategy.get("rationale"), truncate_chars)
    if isinstance(proposed_trade, dict) and "rationale" in proposed_trade:
        proposed_trade = dict(proposed_trade)
        proposed_trade["rationale"] = _truncate_text(proposed_trade.get("rationale"), truncate_chars)

    compact: Dict[str, Any] = {
        "ticker": full.get("ticker"),
        "market": full.get("market"),
        "simulated_date": full.get("simulated_date"),
        "run_config": full.get("run_config"),
        "trading_strategy": trading_strategy if isinstance(trading_strategy, dict) else {},
        "proposed_trade": proposed_trade if isinstance(proposed_trade, dict) else {},
        "risk": {
            "risk_gate": _truncate_text(risk_gate, truncate_chars),
        },
        "memory_id": full.get("memory_id"),
    }

    # Remove noisy/large keys if present
    for noisy_key in [
        "reports",
        "investment_debate_state",
        "arguments",
        "investment_plan",
        "stock_chart_image",
        "sentiment_score",
        "trader_reports",
        "risk_reports",
        "compliance_check",
    ]:
        compact.pop(noisy_key, None)

    return compact


def build_payload(ticker: str, market: str, simulated_date: str, horizon: str, flags: Dict[str, bool]) -> Dict[str, Any]:
    return {
        "ticker": ticker,
        "market": market,
        "simulated_date": simulated_date,
        "horizon": horizon,
        "debate_on": flags.get("debate_on", True),
        "memory_on": flags.get("memory_on", True),
        "risk_on": flags.get("risk_on", True),
        "social_on": flags.get("social_on", False),
    }


def _parse_horizons(horizon: str, horizons: str) -> List[str]:
    """Resolve horizon(s) from CLI args.

    - If `horizons` is provided, it wins.
    - Supports `all` -> short,medium,long.
    """
    if horizons:
        raw = horizons.strip().lower()
        if raw == "all":
            return ["short", "medium", "long"]
        items = [h.strip().lower() for h in raw.split(",") if h.strip()]
        valid = {"short", "medium", "long"}
        bad = [h for h in items if h not in valid]
        if bad:
            raise ValueError(f"Invalid horizon(s): {bad}. Valid: short,medium,long")
        # De-duplicate while preserving order
        seen = set()
        resolved: List[str] = []
        for h in items:
            if h not in seen:
                seen.add(h)
                resolved.append(h)
        return resolved

    # Fallback to single horizon
    return [horizon.strip().lower() or "short"]


def _run_single(
    api_base: str,
    ticker: str,
    simulated_date: str,
    market: str,
    horizon: str,
    flags: Dict[str, bool],
    output_mode: Literal["full", "compact"],
    truncate_chars: int,
) -> Dict[str, Any]:
    """Execute a single analysis call and return the record dict."""
    payload = build_payload(ticker, market, simulated_date, horizon, flags)
    try:
        req = Request(
            url=f"{api_base}/analyze",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=300) as resp:
            body = resp.read().decode("utf-8")
        result = json.loads(body) if body else {}

        stored_result: Any = result
        if output_mode == "compact" and isinstance(result, dict):
            stored_result = compact_result(result, truncate_chars=truncate_chars)

        return {
            "ticker": ticker,
            "simulated_date": simulated_date,
            "horizon": horizon,
            "market": market,
            "flags": flags,
            "result": stored_result,
        }
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ticker": ticker,
            "simulated_date": simulated_date,
            "horizon": horizon,
            "market": market,
            "flags": flags,
            "error": str(exc),
        }


def run_batch(
    api_base: str,
    tickers: List[str],
    dates: List[str],
    market: str,
    horizons: List[str],
    flags: Dict[str, bool],
    out_dir: str,
    tag: str,
    output_mode: Literal["full", "compact"] = "compact",
    truncate_chars: int = 400,
    workers: int = 1,
) -> str:
    ensure_dir(out_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(out_dir, f"batch_{tag}_{timestamp}.jsonl")

    jobs: List[Tuple[str, str, str]] = [(t, d, h) for t in tickers for d in dates for h in horizons]
    total = len(jobs)
    completed = 0

    with open(out_path, "w", encoding="utf-8") as out:
        if workers <= 1:
            # Sequential execution (original behavior)
            for ticker, simulated_date, horizon in jobs:
                record = _run_single(
                    api_base, ticker, simulated_date, market, horizon, flags, output_mode, truncate_chars
                )
                out.write(json.dumps(record) + "\n")
                out.flush()
                completed += 1
                print(f"[{completed}/{total}] {ticker} @ {simulated_date} [{horizon}]")
        else:
            # Parallel execution
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_job = {
                    executor.submit(
                        _run_single,
                        api_base,
                        ticker,
                        simulated_date,
                        market,
                        horizon,
                        flags,
                        output_mode,
                        truncate_chars,
                    ): (ticker, simulated_date, horizon)
                    for ticker, simulated_date, horizon in jobs
                }
                for future in as_completed(future_to_job):
                    ticker, simulated_date, horizon = future_to_job[future]
                    try:
                        record = future.result()
                    except Exception as exc:
                        record = {
                            "ticker": ticker,
                            "simulated_date": simulated_date,
                            "horizon": horizon,
                            "market": market,
                            "flags": flags,
                            "error": str(exc),
                        }
                    out.write(json.dumps(record) + "\n")
                    out.flush()
                    completed += 1
                    print(f"[{completed}/{total}] {ticker} @ {simulated_date} [{horizon}]")

    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run batch NexusTrader analyses.")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="Backend API base URL")
    parser.add_argument("--tickers", default="AAPL,MSFT,NVDA,TSLA", help="Comma-separated tickers")
    parser.add_argument(
        "--tickers-file",
        default=DEFAULT_TICKERS_FILE,
        help="File with one ticker per line (default: nexustrader/experiments/inputs/tickers.txt)",
    )
    parser.add_argument("--dates", default="", help="Comma-separated simulated dates (YYYY-MM-DD)")
    parser.add_argument(
        "--dates-file",
        default=DEFAULT_DATES_FILE,
        help="File with one date per line (default: nexustrader/experiments/inputs/dates.txt)",
    )
    parser.add_argument("--market", default="US", help="Market code")
    parser.add_argument("--horizon", default="short", choices=["short", "medium", "long"], help="Trading horizon")
    parser.add_argument(
        "--horizons",
        default="",
        help="Comma-separated horizons to run in one batch (e.g., short,medium,long) or 'all'",
    )
    parser.add_argument("--debate-on", action="store_true", default=True)
    parser.add_argument("--debate-off", action="store_false", dest="debate_on")
    parser.add_argument("--memory-on", action="store_true", default=True)
    parser.add_argument("--memory-off", action="store_false", dest="memory_on")
    parser.add_argument("--risk-on", action="store_true", default=True)
    parser.add_argument("--risk-off", action="store_false", dest="risk_on")
    parser.add_argument("--social-on", action="store_true", default=False)
    parser.add_argument("--social-off", action="store_false", dest="social_on")
    parser.add_argument("--out", default=DEFAULT_OUT_DIR, help="Output directory")
    parser.add_argument("--tag", default="run", help="Tag to include in output filename")
    parser.add_argument(
        "--output",
        choices=["full", "compact"],
        default="compact",
        help="Write full model output or a compact subset suitable for scoring",
    )
    parser.add_argument(
        "--truncate-chars",
        type=int,
        default=400,
        help="Truncate long text fields in compact output (0 disables truncation)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel workers (1 = sequential, 2-4 recommended)",
    )

    args = parser.parse_args()

    try:
        horizons = _parse_horizons(args.horizon, args.horizons)
    except ValueError as exc:
        print(str(exc))
        return 1

    tickers = load_list_from_file(args.tickers_file) or parse_list(args.tickers)
    dates = load_list_from_file(args.dates_file) or parse_list(args.dates)

    if not tickers:
        print("No tickers provided.")
        return 1
    if not dates:
        print("No dates provided. Use --dates or --dates-file.")
        return 1

    flags = {
        "debate_on": args.debate_on,
        "memory_on": args.memory_on,
        "risk_on": args.risk_on,
        "social_on": args.social_on,
    }

    out_path = run_batch(
        api_base=args.api,
        tickers=tickers,
        dates=dates,
        market=args.market,
        horizons=horizons,
        flags=flags,
        out_dir=args.out,
        tag=args.tag,
        output_mode=args.output,
        truncate_chars=args.truncate_chars,
        workers=args.workers,
    )

    print(f"Batch completed. Results saved to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
