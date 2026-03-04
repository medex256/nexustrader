import pandas as pd

df = pd.read_csv("results/scored/agent_runs_scored_registry.csv")
v21 = df[df.run_tag == "eval50_v2.1_gm-3-fpro"]
v2 = df[df.run_tag == "eval50_v2_gm-3-flash"]

v2_keys = set(zip(v2.ticker, v2.simulated_date))
v21_keys = set(zip(v21.ticker, v21.simulated_date))
missing = v2_keys - v21_keys
print("Missing in v2.1:", missing)

print("\nv2.1 HOLD rows:")
print(v21[v21.action == "HOLD"][["ticker", "simulated_date", "action", "k_return", "correct"]].to_string())

# Paired comparison
merged = v2.merge(v21, on=["ticker", "simulated_date", "horizon"], suffixes=("_v2", "_v21"))
merged["both_correct"] = (merged.correct_v2 == 1) & (merged.correct_v21 == 1)
merged["v2_only_correct"] = (merged.correct_v2 == 1) & (merged.correct_v21 == 0)
merged["v21_only_correct"] = (merged.correct_v2 == 0) & (merged.correct_v21 == 1)
merged["both_wrong"] = (merged.correct_v2 == 0) & (merged.correct_v21 == 0)

print("\n=== Paired disagreement matrix ===")
print(f"Both correct: {merged.both_correct.sum()}")
print(f"v2 correct, v2.1 wrong: {merged.v2_only_correct.sum()}")
print(f"v2.1 correct, v2 wrong: {merged.v21_only_correct.sum()}")
print(f"Both wrong: {merged.both_wrong.sum()}")
print(f"Total paired: {len(merged)}")

# Where did pro FLIP the action vs flash?
flipped = merged[merged.action_v2 != merged.action_v21]
print(f"\n=== Action flips (v2 flash → v2.1 pro): {len(flipped)} ===")
for _, r in flipped.iterrows():
    print(f"  {r.ticker} {r.simulated_date}: {r.action_v2} → {r.action_v21} | k_return={r.k_return_v2:.3f} | v2 correct={int(r.correct_v2)}, v2.1 correct={int(r.correct_v21)}")
