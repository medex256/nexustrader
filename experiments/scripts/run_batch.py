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
DEFAULT_DATES_FILE = os.path.join(EXPERIMENTS_DIR, "inputs", "dates_expanded.txt")
DEFAULT_OUT_DIR = os.path.join(EXPERIMENTS_DIR, "results", "raw")
DEFAULT_TRACE_OUT_DIR = os.path.join(EXPERIMENTS_DIR, "results", "traces")
SCHEMA_VERSION = "2.0"

STAGE_PRESETS = {
    "A": {"debate_mode": "off", "debate_rounds": 0, "risk_debate_rounds": 0, "risk_mode": "off", "memory_on": False},
    "B": {"debate_mode": "on", "debate_rounds": 1, "risk_debate_rounds": 0, "risk_mode": "off", "memory_on": False},
    "B+": {"debate_mode": "on", "debate_rounds": 1, "risk_debate_rounds": 0, "risk_mode": "single", "memory_on": False},
    "C": {"debate_mode": "on", "debate_rounds": 1, "risk_debate_rounds": 1, "risk_mode": "debate", "memory_on": False},
    "D": {"debate_mode": "on", "debate_rounds": 1, "risk_debate_rounds": 1, "risk_mode": "debate", "memory_on": True},
}


def _normalize_stage(stage: str | None) -> str | None:
    if not stage:
        return None
    normalized = stage.strip().upper()
    if normalized == "BPLUS":
        return "B+"
    return normalized if normalized in STAGE_PRESETS else None


def _resolve_flags(args: argparse.Namespace) -> Dict[str, Any]:
    stage_key = _normalize_stage(getattr(args, "stage", None))
    if stage_key:
        preset = STAGE_PRESETS[stage_key]
        risk_rounds = int(getattr(args, "risk_debate_rounds", preset.get("risk_debate_rounds", 0)) or 0)
        if preset["risk_mode"] != "debate":
            risk_rounds = 0
        elif risk_rounds < 1:
            risk_rounds = 1
        return {
            "stage": stage_key,
            "debate_rounds": preset["debate_rounds"],
            "risk_debate_rounds": risk_rounds,
            "debate_mode": preset["debate_mode"],
            "decision_style": args.decision_style,
            "memory_on": preset["memory_on"],
            "risk_mode": preset["risk_mode"],
            "use_pro_stage_a_manager": args.use_pro_stage_a_manager,
            "use_cached_stage_a_reports": args.use_cached_stage_a_reports,
            "use_cached_stage_a_prior": args.use_cached_stage_a_prior,
            "cache_trace_file": args.cache_trace_file,
        }

    risk_mode = args.risk_mode if args.risk_mode is not None else ("single" if args.risk_on else "off")
    if risk_mode not in {"off", "single", "debate"}:
        risk_mode = "single"
    debate_mode = (args.debate_mode or "on").strip().lower()
    if debate_mode not in {"on", "off"}:
        debate_mode = "on"
    debate_rounds = args.debate_rounds if debate_mode == "on" else 0
    risk_debate_rounds = max(0, int(getattr(args, "risk_debate_rounds", 0) or 0))
    if risk_mode != "debate":
        risk_debate_rounds = 0
    elif risk_debate_rounds < 1:
        risk_debate_rounds = 1

    return {
        "stage": None,
        "debate_rounds": debate_rounds,
        "risk_debate_rounds": risk_debate_rounds,
        "debate_mode": debate_mode,
        "decision_style": args.decision_style,
        "memory_on": args.memory_on,
        "risk_mode": risk_mode,
        "use_pro_stage_a_manager": args.use_pro_stage_a_manager,
        "use_cached_stage_a_reports": args.use_cached_stage_a_reports,
        "use_cached_stage_a_prior": args.use_cached_stage_a_prior,
        "cache_trace_file": args.cache_trace_file,
    }


def parse_list(arg: str) -> List[str]:
    if not arg:
        return []
    return [item.strip() for item in arg.split(",") if item.strip()]


def load_list_from_file(path: str) -> List[str]:
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_pairs_from_file(path: str) -> List[Tuple[str, str]]:
    if not path:
        return []

    pairs: List[Tuple[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            parts = [part.strip() for part in raw.split(",")]
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(
                    f"Invalid ticker/date pair on line {line_no} in {path!r}: {raw!r}. "
                    "Expected format: TICKER,YYYY-MM-DD"
                )
            pairs.append((parts[0], parts[1]))
    return pairs


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


def _extract_risk_judgment(compact_or_full_result: Dict[str, Any]) -> str:
    strategy = _safe_get(compact_or_full_result, "trading_strategy", default={}) or {}
    rationale = str(strategy.get("rationale") or "")
    for tag in ("[BLOCK]", "[REDUCE]", "[CLEAR]"):
        if tag in rationale:
            return tag.strip("[]")
    return "UNKNOWN"


def build_result_summary(compact_or_full_result: Dict[str, Any]) -> Dict[str, Any]:
    strategy = _safe_get(compact_or_full_result, "trading_strategy", default={}) or {}
    risk_gate = _safe_get(compact_or_full_result, "risk", "risk_gate", default="")
    if not risk_gate:
        risk_gate = _safe_get(compact_or_full_result, "risk_reports", "risk_gate", default="")
    return {
        "action": (strategy.get("action") or "HOLD"),
        "confidence_score": strategy.get("confidence_score"),
        "position_size_pct": strategy.get("position_size_pct"),
        "risk_judgment": _extract_risk_judgment(compact_or_full_result),
        "risk_gate": risk_gate,
    }


def trace_result(full: Dict[str, Any], request_payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ticker": full.get("ticker") or request_payload.get("ticker"),
        "simulated_date": full.get("simulated_date") or request_payload.get("simulated_date"),
        "horizon": request_payload.get("horizon"),
        "market": full.get("market") or request_payload.get("market"),
        "request_payload": request_payload,
        "trace": {
            "run_config": full.get("run_config"),
            "signals": full.get("signals"),
            "reports": full.get("reports"),
            "investment_debate_state": full.get("investment_debate_state"),
            "investment_plan": full.get("investment_plan"),
            "investment_plan_structured": full.get("investment_plan_structured"),
            "research_manager_recommendation": full.get("research_manager_recommendation"),
            "trading_strategy": full.get("trading_strategy"),
            "risk_reports": full.get("risk_reports"),
            "compliance_check": full.get("compliance_check"),
            "analysis_time_seconds": full.get("analysis_time_seconds"),
            "memory_id": full.get("memory_id"),
            "provenance": full.get("provenance"),
        },
    }


def build_payload(ticker: str, market: str, simulated_date: str, horizon: str, flags: Dict[str, Any]) -> Dict[str, Any]:
    risk_mode = (flags.get("risk_mode") or "off").strip().lower()
    if risk_mode not in {"off", "single", "debate"}:
        risk_mode = "single"
    debate_mode = (flags.get("debate_mode") or "on").strip().lower()
    if debate_mode not in {"on", "off"}:
        debate_mode = "on"
    debate_rounds = 0 if debate_mode == "off" else flags.get("debate_rounds", 1)
    risk_debate_rounds = int(flags.get("risk_debate_rounds", 0) or 0)
    if risk_mode != "debate":
        risk_debate_rounds = 0
    elif risk_debate_rounds < 1:
        risk_debate_rounds = 1

    return {
        "ticker": ticker,
        "market": market,
        "simulated_date": simulated_date,
        "horizon": horizon,
        "stage": flags.get("stage"),
        "debate_rounds": debate_rounds,
        "risk_debate_rounds": risk_debate_rounds,
        "debate_mode": debate_mode,
        "decision_style": flags.get("decision_style", "classification"),
        "memory_on": flags.get("memory_on", True),
        "risk_mode": risk_mode,
        "use_pro_stage_a_manager": flags.get("use_pro_stage_a_manager", False),
        "use_cached_stage_a_reports": flags.get("use_cached_stage_a_reports", False),
        "use_cached_stage_a_prior": flags.get("use_cached_stage_a_prior", False),
        "cache_trace_file": flags.get("cache_trace_file"),
    }


def _validate_horizon(horizon: str) -> str:
    """Validate and return a single horizon for the experiment.
    
    Single-horizon design ensures clean i.i.d. benchmarks without 
    confounding from multi-horizon mixing.
    """
    h = horizon.strip().lower()
    valid = {"short", "medium", "long"}
    if h not in valid:
        raise ValueError(f"Invalid horizon '{h}'. Valid: short, medium, long")
    return h


def _run_single(
    api_base: str,
    ticker: str,
    simulated_date: str,
    market: str,
    horizon: str,
    flags: Dict[str, Any],
    output_mode: Literal["full", "compact", "dual"],
    truncate_chars: int,
    retries: int = 2,
) -> Dict[str, Any]:
    """Execute a single analysis call and return the record dict."""
    payload = build_payload(ticker, market, simulated_date, horizon, flags)
    total_attempts = max(1, retries + 1)
    last_exc: Exception | None = None

    for attempt in range(1, total_attempts + 1):
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
            if output_mode in {"compact", "dual"} and isinstance(result, dict):
                stored_result = compact_result(result, truncate_chars=truncate_chars)

            record = {
                "schema_version": SCHEMA_VERSION,
                "meta": {
                    "schema_version": SCHEMA_VERSION,
                    "script": "run_batch.py",
                    "output_mode": output_mode,
                    "status": "ok",
                },
                "request": payload,
                "result_summary": build_result_summary(stored_result if isinstance(stored_result, dict) else {}),
                "ticker": ticker,
                "simulated_date": simulated_date,
                "horizon": horizon,
                "market": market,
                "flags": flags,
                "attempt": attempt,
                "result": stored_result,
            }
            if output_mode == "dual" and isinstance(result, dict):
                record["_trace_record"] = {
                    "schema_version": SCHEMA_VERSION,
                    "meta": {
                        "schema_version": SCHEMA_VERSION,
                        "script": "run_batch.py",
                        "output_mode": output_mode,
                        "status": "ok",
                    },
                    "ticker": ticker,
                    "simulated_date": simulated_date,
                    "horizon": horizon,
                    "market": market,
                    "flags": flags,
                    "attempt": attempt,
                    **trace_result(result, payload),
                }

            return record
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_exc = exc
            continue

    return {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "script": "run_batch.py",
            "output_mode": output_mode,
            "status": "error",
        },
        "request": payload,
        "result_summary": {
            "action": "ERROR",
            "confidence_score": None,
            "position_size_pct": None,
            "risk_judgment": "UNKNOWN",
            "risk_gate": "",
        },
        "ticker": ticker,
        "simulated_date": simulated_date,
        "horizon": horizon,
        "market": market,
        "flags": flags,
        "attempt": total_attempts,
        "error": str(last_exc) if last_exc is not None else "unknown_error",
    }


def run_batch(
    api_base: str,
    tickers: List[str],
    dates: List[str],
    market: str,
    horizon: str,
    flags: Dict[str, Any],
    out_dir: str,
    tag: str,
    output_mode: Literal["full", "compact", "dual"] = "compact",
    trace_out_dir: str | None = None,
    truncate_chars: int = 400,
    workers: int = 1,
    retries: int = 2,
    jobs: List[Tuple[str, str]] | None = None,
) -> Tuple[str, str | None]:
    ensure_dir(out_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(out_dir, f"batch_{tag}_{timestamp}.jsonl")
    trace_path = None
    if output_mode == "dual":
        trace_dir = trace_out_dir or DEFAULT_TRACE_OUT_DIR
        ensure_dir(trace_dir)
        trace_path = os.path.join(trace_dir, f"batch_{tag}_trace_{timestamp}.jsonl")

    jobs = jobs if jobs is not None else [(t, d) for t in tickers for d in dates]
    total = len(jobs)
    completed = 0

    with open(out_path, "w", encoding="utf-8") as out, (
        open(trace_path, "w", encoding="utf-8") if trace_path else open(os.devnull, "w", encoding="utf-8")
    ) as trace_out:
        if workers <= 1:
            # Sequential execution (original behavior)
            for ticker, simulated_date in jobs:
                record = _run_single(
                    api_base, ticker, simulated_date, market, horizon, flags, output_mode, truncate_chars, retries
                )
                trace_record = record.pop("_trace_record", None)
                out.write(json.dumps(record) + "\n")
                out.flush()
                if trace_record is not None:
                    trace_out.write(json.dumps(trace_record) + "\n")
                    trace_out.flush()
                completed += 1
                print(f"[{completed}/{total}] {ticker} @ {simulated_date} [horizon={horizon}]")
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
                        retries,
                    ): (ticker, simulated_date)
                    for ticker, simulated_date in jobs
                }
                for future in as_completed(future_to_job):
                    ticker, simulated_date = future_to_job[future]
                    try:
                        record = future.result()
                    except Exception as exc:
                        payload = build_payload(ticker, market, simulated_date, horizon, flags)
                        record = {
                            "schema_version": SCHEMA_VERSION,
                            "meta": {
                                "schema_version": SCHEMA_VERSION,
                                "script": "run_batch.py",
                                "output_mode": output_mode,
                                "status": "error",
                            },
                            "request": payload,
                            "result_summary": {
                                "action": "ERROR",
                                "confidence_score": None,
                                "position_size_pct": None,
                                "risk_judgment": "UNKNOWN",
                                "risk_gate": "",
                            },
                            "ticker": ticker,
                            "simulated_date": simulated_date,
                            "horizon": horizon,
                            "market": market,
                            "flags": flags,
                            "error": str(exc),
                        }
                    trace_record = record.pop("_trace_record", None)
                    out.write(json.dumps(record) + "\n")
                    out.flush()
                    if trace_record is not None:
                        trace_out.write(json.dumps(trace_record) + "\n")
                        trace_out.flush()
                    completed += 1
                    print(f"[{completed}/{total}] {ticker} @ {simulated_date} [horizon={horizon}]")

    return out_path, trace_path


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
    parser.add_argument(
        "--pairs-file",
        default="",
        help="File with one TICKER,YYYY-MM-DD pair per line. If provided, runs exactly those rows instead of a ticker × date cartesian product.",
    )
    parser.add_argument("--market", default="US", help="Market code")
    parser.add_argument(
        "--horizon",
        default="short",
        choices=["short", "medium", "long"],
        help="Trading horizon (single-horizon experiment design; k=10 for short, k=21 for medium, k=126 for long)",
    )
    parser.add_argument(
        "--stage",
        choices=["A", "B", "B+", "C", "D", "bplus", "BPLUS"],
        default=None,
        help="Stage preset override: A(core), B(+debate), B+(+single risk), C(+risk debate), D(+memory).",
    )
    parser.add_argument("--debate-rounds", type=int, default=1, help="Number of debate rounds (0, 1, or 2)")
    parser.add_argument(
        "--risk-debate-rounds",
        type=int,
        default=1,
        help="Number of risk debate rounds when risk_mode=debate (1 or 2).",
    )
    parser.add_argument(
        "--debate-mode",
        choices=["on", "off"],
        default="on",
        help="Investment debate mode: on (Bull/Bear enabled) or off (bypass to judge)",
    )
    parser.add_argument(
        "--decision-style",
        choices=["classification", "full"],
        default="classification",
        help="classification: focus on 10-day UP/DOWN/HOLD; full: include richer trade fields",
    )
    parser.add_argument("--memory-on", action="store_true", default=True)
    parser.add_argument("--memory-off", action="store_false", dest="memory_on")
    parser.add_argument("--risk-on", action="store_true", default=False)
    parser.add_argument("--risk-off", action="store_false", dest="risk_on")
    parser.add_argument(
        "--risk-mode",
        choices=["off", "single", "debate"],
        default=None,
        help="Risk stage mode: off (skip), single (risk manager only), debate (3 risk agents + manager)",
    )
    parser.add_argument("--out", default=DEFAULT_OUT_DIR, help="Output directory")
    parser.add_argument("--tag", default="experiment", help="Tag to include in output filename (e.g., baseline, memory_on, debate_2)")
    parser.add_argument(
        "--output",
        choices=["full", "compact", "dual"],
        default="compact",
        help="compact: lean scorer file, full: full backend response in raw JSONL, dual: compact raw JSONL plus separate trace JSONL",
    )
    parser.add_argument(
        "--trace-out",
        default=DEFAULT_TRACE_OUT_DIR,
        help="Output directory for trace JSONL files when --output dual is used",
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
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retries per failed request (improves completeness)",
    )
    parser.add_argument(
        "--use-pro-stage-a-manager",
        action="store_true",
        default=False,
        help="Use Gemini Pro for Stage A Research Manager call only (all other calls remain Flash)",
    )
    parser.add_argument(
        "--use-cached-stage-a-reports",
        action="store_true",
        default=False,
        help="Load cached analyst reports/signals from a Stage A trace batch and skip analyst LLM calls",
    )
    parser.add_argument(
        "--use-cached-stage-a-prior",
        action="store_true",
        default=False,
        help="Load cached Stage A manager decision from a Stage A trace batch for frozen Stage B prior evaluation",
    )
    parser.add_argument(
        "--cache-trace-file",
        default="",
        help="Path to a Stage A trace JSONL file produced with --output dual",
    )

    args = parser.parse_args()

    # Resolve cache_trace_file to an absolute path so the backend (which runs
    # from a different CWD) can always find the file.
    if args.cache_trace_file:
        args.cache_trace_file = os.path.abspath(args.cache_trace_file)

    try:
        horizon = _validate_horizon(args.horizon)
    except ValueError as exc:
        print(str(exc))
        return 1

    try:
        pair_jobs = load_pairs_from_file(args.pairs_file) if args.pairs_file else []
    except ValueError as exc:
        print(str(exc))
        return 1

    tickers = load_list_from_file(args.tickers_file) or parse_list(args.tickers)
    dates = load_list_from_file(args.dates_file) or parse_list(args.dates)

    if not pair_jobs:
        if not tickers:
            print("No tickers provided.")
            return 1
        if not dates:
            print("No dates provided. Use --dates or --dates-file.")
            return 1

    flags = _resolve_flags(args)

    out_path, trace_path = run_batch(
        api_base=args.api,
        tickers=tickers,
        dates=dates,
        market=args.market,
        horizon=horizon,
        flags=flags,
        out_dir=args.out,
        tag=args.tag,
        output_mode=args.output,
        trace_out_dir=args.trace_out,
        truncate_chars=args.truncate_chars,
        workers=args.workers,
        retries=max(0, args.retries),
        jobs=pair_jobs or None,
    )

    print(f"Batch completed. Results saved to: {out_path}")
    if trace_path:
        print(f"Trace cache saved to: {trace_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
