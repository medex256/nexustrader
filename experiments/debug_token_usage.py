#!/usr/bin/env python3
"""
Debug script: Run a single Stage C analysis and report token usage per LLM call.

Usage:
    python debug_token_usage.py --ticker NVDA --date 2025-02-24 [--use-cache]
"""

import sys
import json
import argparse
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import os
os.chdir(backend_path)

from app.llm import reset_token_log, get_token_log
from app.main import app
from fastapi.testclient import TestClient


def run_single_debug_analysis(
    ticker: str,
    date: str,
    use_cache: bool = False,
    tag: str = "debug_token_trace",
):
    """Run a single Stage C analysis and log token usage."""
    
    # Reset token log before run
    reset_token_log()
    
    client = TestClient(app)
    
    payload = {
        "ticker": ticker,
        "market": "US",
        "simulated_date": date,
        "horizon": "short",
        "stage": "C",
        "debate_rounds": 1,
        "risk_debate_rounds": 1,
        "debate_mode": "on",
        "decision_style": "classification",
        "memory_on": False,
        "risk_mode": "debate",
        "use_pro_stage_a_manager": False,
    }
    
    if use_cache:
        cache_file = Path(__file__).parent / "results" / "traces" / "batch_final_eval385_stageA_new_v2_trace_20260313_154152.jsonl"
        if cache_file.exists():
            payload["use_cached_stage_a_reports"] = True
            payload["use_cached_stage_a_prior"] = True
            payload["cache_trace_file"] = str(cache_file)
            print(f"✓ Using cached Stage A trace: {cache_file.name}")
        else:
            print(f"⚠ Cache file not found: {cache_file}")
            print("  Running without Stage A cache...")
    
    print(f"\n📊 Running Stage C analysis for {ticker} on {date}...")
    print("-" * 70)
    
    try:
        response = client.post("/analyze", json=payload)
        if response.status_code != 200:
            print(f"❌ Analysis failed with status {response.status_code}")
            print(response.text)
            return
        
        result = response.json()
        
        # Extract decision
        action = result.get("result_summary", {}).get("action", "UNKNOWN")
        confidence = result.get("result_summary", {}).get("confidence_score", 0)
        risk_judgment = result.get("result_summary", {}).get("risk_judgment", "UNKNOWN")
        
        print(f"\n✅ Analysis Complete")
        print(f"   Action: {action} | Confidence: {confidence} | Risk: {risk_judgment}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    # Get and display token log
    token_log = get_token_log()
    
    if not token_log:
        print("\n⚠️  No token usage data captured.")
        print("   This may mean: (a) provider mode doesn't support token reporting,")
        print("   or (b) calls used Vertex API key mode (no usage metadata).")
        return
    
    print(f"\n📈 Token Usage Summary ({len(token_log)} LLM calls)")
    print("=" * 70)
    print(f"{'Call Name':<40} {'Input':>10} {'Output':>10} {'Total':>10}")
    print("-" * 70)
    
    total_input = 0
    total_output = 0
    total_calls = 0
    
    for log_entry in token_log:
        call = log_entry["call"]
        in_tk = log_entry["input"]
        out_tk = log_entry["output"]
        tot_tk = log_entry["total"]
        
        # Truncate call name if too long
        call_display = call if len(call) <= 39 else call[:36] + "..."
        
        print(f"{call_display:<40} {in_tk:>10,} {out_tk:>10,} {tot_tk:>10,}")
        
        total_input += in_tk
        total_output += out_tk
        total_calls += 1
    
    print("-" * 70)
    print(f"{'TOTAL':<40} {total_input:>10,} {total_output:>10,} {total_input + total_output:>10,}")
    print("=" * 70)
    
    print(f"\n💰 Cost Estimate (Gemini Flash)")
    input_cost = (total_input / 1_000_000) * 0.075  # $0.075 per 1M input
    output_cost = (total_output / 1_000_000) * 0.30  # $0.30 per 1M output
    total_cost = input_cost + output_cost
    print(f"   Input:  {total_input:>8,} tokens × $0.075/1M = ${input_cost:.6f}")
    print(f"   Output: {total_output:>8,} tokens × $0.30/1M  = ${output_cost:.6f}")
    print(f"   Total:                             ${total_cost:.6f}\n")
    
    return {
        "ticker": ticker,
        "date": date,
        "action": action,
        "total_calls": total_calls,
        "total_input": total_input,
        "total_output": total_output,
        "total_tokens": total_input + total_output,
        "cost_usd": total_cost,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Debug token usage for Stage C single run")
    parser.add_argument("--ticker", default="NVDA", help="Ticker symbol")
    parser.add_argument("--date", default="2025-02-24", help="Simulated date (YYYY-MM-DD)")
    parser.add_argument("--use-cache", action="store_true", help="Use cached Stage A reports")
    parser.add_argument("--tag", default="debug_token_trace", help="Run tag")
    
    args = parser.parse_args()
    
    result = run_single_debug_analysis(
        ticker=args.ticker,
        date=args.date,
        use_cache=args.use_cache,
        tag=args.tag,
    )
