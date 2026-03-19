import argparse
import json
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict
from urllib.request import Request, urlopen

from run_batch import SCHEMA_VERSION, _resolve_flags, _validate_horizon, build_payload, build_result_summary


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPERIMENTS_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_OUT_DIR = os.path.join(EXPERIMENTS_DIR, "results", "debug")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _safe_slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text or "")


def run_single(api_base: str, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    req = Request(
        url=f"{api_base}/analyze",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body) if body else {}


def build_trace_sections(final_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "run_config": final_state.get("run_config"),
        "signals": final_state.get("signals"),
        "reports": final_state.get("reports"),
        "investment_debate_state": final_state.get("investment_debate_state"),
        "investment_plan": final_state.get("investment_plan"),
        "investment_plan_structured": final_state.get("investment_plan_structured"),
        "research_manager_recommendation": final_state.get("research_manager_recommendation"),
        "trading_strategy": final_state.get("trading_strategy"),
        "risk_reports": final_state.get("risk_reports"),
        "compliance_check": final_state.get("compliance_check"),
        "analysis_time_seconds": final_state.get("analysis_time_seconds"),
        "memory_id": final_state.get("memory_id"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one NexusTrader analysis and save full debug trace JSON."
    )
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="Backend API base URL")
    parser.add_argument("--ticker", required=True, help="Ticker symbol, e.g. NVDA")
    parser.add_argument("--date", required=True, help="Simulated date (YYYY-MM-DD)")
    parser.add_argument("--market", default="US", help="Market code")
    parser.add_argument(
        "--horizon",
        default="short",
        choices=["short", "medium", "long"],
        help="Trading horizon",
    )
    parser.add_argument(
        "--stage",
        choices=["A", "B", "B+", "C", "D", "bplus", "BPLUS"],
        default="A",
        help="Stage preset",
    )
    parser.add_argument("--debate-rounds", type=int, default=1)
    parser.add_argument(
        "--risk-debate-rounds",
        type=int,
        default=1,
        help="Number of risk debate rounds when risk_mode=debate (1 or 2).",
    )
    parser.add_argument("--debate-mode", choices=["on", "off"], default="on")
    parser.add_argument("--decision-style", choices=["classification", "full"], default="classification")
    parser.add_argument("--memory-on", action="store_true", default=True)
    parser.add_argument("--memory-off", action="store_false", dest="memory_on")
    parser.add_argument("--risk-on", action="store_true", default=False)
    parser.add_argument("--risk-off", action="store_false", dest="risk_on")
    parser.add_argument("--risk-mode", choices=["off", "single", "debate"], default=None)
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
        help="Load cached Stage A manager decision from a Stage A trace batch",
    )
    parser.add_argument(
        "--cache-trace-file",
        default="",
        help="Path to a Stage A trace JSONL file produced with run_batch --output dual",
    )
    parser.add_argument("--timeout", type=int, default=600, help="HTTP timeout seconds")
    parser.add_argument("--out", default=DEFAULT_OUT_DIR, help="Output directory for debug JSON")
    parser.add_argument("--tag", default="manual", help="Tag in output filename")

    args = parser.parse_args()

    try:
        horizon = _validate_horizon(args.horizon)
    except ValueError as exc:
        print(str(exc))
        return 1

    if args.cache_trace_file:
        args.cache_trace_file = os.path.abspath(args.cache_trace_file)

    flags = _resolve_flags(args)
    payload = build_payload(
        ticker=args.ticker.upper(),
        market=args.market,
        simulated_date=args.date,
        horizon=horizon,
        flags=flags,
    )

    started_at = datetime.now().isoformat(timespec="seconds")
    try:
        final_state = run_single(args.api, payload, timeout=args.timeout)
    except Exception as exc:
        print(f"Run failed: {exc}")
        return 1

    ended_at = datetime.now().isoformat(timespec="seconds")
    trace = build_trace_sections(final_state)

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "created_at": ended_at,
            "started_at": started_at,
            "api": args.api,
            "script": "run_single.py",
            "tag": args.tag,
        },
        "request": payload,
        "result_summary": build_result_summary(final_state),
        "request_payload": payload,
        "response_full": final_state,
        "trace": trace,
    }

    ensure_dir(args.out)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"single_{_safe_slug(args.tag)}_{_safe_slug(args.ticker.upper())}_{_safe_slug(args.date)}_{ts}.json"
    out_path = os.path.join(args.out, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False, default=str)

    print("Saved debug artifact:")
    print(out_path)
    print("\nQuick summary:")
    print(f"- action: {((final_state.get('trading_strategy') or {}).get('action') or 'N/A')}")
    print(f"- has reports: {isinstance(final_state.get('reports'), dict)}")
    print(f"- has signals: {isinstance(final_state.get('signals'), dict)}")
    print(f"- has investment_plan: {bool(final_state.get('investment_plan'))}")
    print(f"- has risk_reports: {isinstance(final_state.get('risk_reports'), dict)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
