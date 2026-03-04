"""Temporary script to trace where HOLD decisions originate."""
import json

rows = [json.loads(l) for l in open("results/raw/batch_eval50_g-3-f_structured_debate_20260303_155108.jsonl")]

rm_holds = 0
tr_holds = 0
both_holds = 0
rm_dir_tr_hold = 0
rm_hold_tr_dir = 0
total = 0
disagreed = 0

for r in rows:
    d = r.get("result", {})
    ip = d.get("investment_plan", "")
    ts = d.get("trading_strategy", {})
    
    rm_act = "HOLD"
    tr_act = (ts.get("action", "HOLD") or "HOLD").upper()
    
    try:
        p = json.loads(ip)
        rm_act = (p.get("recommendation", "HOLD") or "HOLD").upper()
    except Exception:
        pass
    
    total += 1
    if rm_act == "HOLD":
        rm_holds += 1
    if tr_act == "HOLD":
        tr_holds += 1
    if rm_act == "HOLD" and tr_act == "HOLD":
        both_holds += 1
    if rm_act != "HOLD" and tr_act == "HOLD":
        rm_dir_tr_hold += 1
    if rm_act == "HOLD" and tr_act != "HOLD":
        rm_hold_tr_dir += 1
    if rm_act != tr_act:
        disagreed += 1

print(f"Total:                       {total}")
print(f"RM HOLD:                     {rm_holds} ({rm_holds/total*100:.0f}%)")
print(f"TR HOLD:                     {tr_holds} ({tr_holds/total*100:.0f}%)")
print(f"Both HOLD:                   {both_holds}")
print(f"RM directional, TR chose HOLD: {rm_dir_tr_hold}")
print(f"RM HOLD, TR chose directional: {rm_hold_tr_dir}")
print(f"Disagreed:                   {disagreed}")

# Check confidence scores in structured plan
print("\n=== RM Confidence Distribution ===")
rm_confs = []
for r in rows:
    d = r.get("result", {})
    ip = d.get("investment_plan", "")
    try:
        p = json.loads(ip)
        conf = p.get("confidence_score", p.get("confidence", "?"))
        buy_s = p.get("buy_score", "?")
        sell_s = p.get("sell_score", "?")
        rec = p.get("recommendation", "?")
        spread = None
        if isinstance(buy_s, (int, float)) and isinstance(sell_s, (int, float)):
            spread = buy_s - sell_s
        print(f"  {r.get('ticker','?')} {r.get('simulated_date','?')}: rec={rec} buy={buy_s} sell={sell_s} spread={spread} conf={conf}")
    except Exception:
        print(f"  {r.get('ticker','?')} {r.get('simulated_date','?')}: [parse failed]")
