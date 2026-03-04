"""Inspect HOLD rationales from batch output."""
import json

rows = [json.loads(l) for l in open("results/raw/batch_eval50_g-3-f_structured_debate_20260303_155108.jsonl")]

holds = 0
buys = 0
sells = 0
total = 0

for r in rows:
    ts = r.get("result", {}).get("trading_strategy", {})
    a = (ts.get("action", "HOLD") or "HOLD").upper()
    total += 1
    if a == "HOLD":
        holds += 1
    elif a == "BUY":
        buys += 1
    elif a == "SELL":
        sells += 1

print(f"Total: {total}  BUY: {buys}  SELL: {sells}  HOLD: {holds}")

print("\n=== Sample HOLD rationales ===")
ct = 0
for r in rows:
    ts = r.get("result", {}).get("trading_strategy", {})
    if (ts.get("action", "").upper() == "HOLD") and ct < 8:
        print(f"\n  {r['ticker']} {r['simulated_date']}:")
        print(f"    rationale: {ts.get('rationale', '')[:300]}")
        print(f"    confidence: {ts.get('confidence_score', 'N/A')}")
        ct += 1

print("\n=== Sample BUY/SELL rationales ===")
ct = 0
for r in rows:
    ts = r.get("result", {}).get("trading_strategy", {})
    if (ts.get("action", "").upper() in ("BUY", "SELL")) and ct < 5:
        print(f"\n  {r['ticker']} {r['simulated_date']}: {ts.get('action')}")
        print(f"    rationale: {ts.get('rationale', '')[:300]}")
        print(f"    confidence: {ts.get('confidence_score', 'N/A')}")
        ct += 1

# Check run_config to see if debate_mode was set
print("\n=== Run Config (first row) ===")
rc = rows[0].get("result", {}).get("run_config", {})
print(json.dumps(rc, indent=2))
