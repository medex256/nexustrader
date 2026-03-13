import json
import os
from functools import lru_cache
from typing import Any, Dict, Optional


def build_stage_a_cache_key(
    ticker: str,
    simulated_date: Optional[str],
    horizon: str,
    market: str,
) -> str:
    return "|".join(
        [
            (ticker or "").strip().upper(),
            (simulated_date or "").strip(),
            (horizon or "").strip().lower(),
            (market or "").strip().upper(),
        ]
    )


def _normalize_trace_path(cache_trace_file: str) -> str:
    return os.path.abspath(os.path.expanduser((cache_trace_file or "").strip()))


@lru_cache(maxsize=8)
def load_stage_a_trace_index(cache_trace_file: str) -> Dict[str, Dict[str, Any]]:
    path = _normalize_trace_path(cache_trace_file)
    if not path:
        raise FileNotFoundError("cache_trace_file is empty")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Stage A trace file not found: {path}")

    index: Dict[str, Dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue

            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no} in {path}: {exc}") from exc

            if row.get("error"):
                continue

            payload = row.get("request_payload") or {}
            ticker = payload.get("ticker") or row.get("ticker")
            simulated_date = payload.get("simulated_date") or row.get("simulated_date")
            horizon = payload.get("horizon") or row.get("horizon")
            market = payload.get("market") or row.get("market")

            if not all([ticker, simulated_date, horizon, market]):
                continue

            key = build_stage_a_cache_key(ticker, simulated_date, horizon, market)
            index[key] = row

    return index


def get_cached_stage_a_trace(
    cache_trace_file: str,
    *,
    ticker: str,
    simulated_date: Optional[str],
    horizon: str,
    market: str,
) -> Optional[Dict[str, Any]]:
    key = build_stage_a_cache_key(ticker, simulated_date, horizon, market)
    return load_stage_a_trace_index(cache_trace_file).get(key)


def extract_cached_reports(trace_row: Dict[str, Any]) -> Dict[str, str]:
    trace = trace_row.get("trace") or {}
    reports = trace.get("reports") or {}
    return dict(reports) if isinstance(reports, dict) else {}


def extract_cached_signals(trace_row: Dict[str, Any]) -> Dict[str, Any]:
    trace = trace_row.get("trace") or {}
    signals = trace.get("signals") or {}
    return dict(signals) if isinstance(signals, dict) else {}


def extract_cached_stage_a_prior(trace_row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    trace = trace_row.get("trace") or {}
    structured = trace.get("investment_plan_structured") or {}
    recommendation = structured.get("recommendation") or trace.get("research_manager_recommendation")
    if recommendation not in {"BUY", "SELL", "HOLD"}:
        return None

    confidence_score = structured.get("confidence_score")
    if confidence_score is None:
        confidence_score = (trace.get("trading_strategy") or {}).get("confidence_score")
    if confidence_score is None:
        confidence_score = 0.5

    primary_drivers = structured.get("primary_drivers") or []
    if not primary_drivers:
        rationale = (trace.get("trading_strategy") or {}).get("rationale")
        if rationale:
            primary_drivers = [rationale[:240]]

    main_risk = structured.get("main_risk") or "Unknown"

    return {
        "recommendation": recommendation,
        "confidence_score": float(confidence_score),
        "primary_drivers": list(primary_drivers),
        "main_risk": main_risk,
    }