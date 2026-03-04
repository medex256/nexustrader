import pandas as pd

df = pd.read_csv("results/scored/agent_runs_scored_registry.csv")
print("All tags:")
print(df["run_tag"].value_counts())

tags = ["eval50_v2.1_gm-3-fpro", "eval50_v2_gm-3-flash", "eval50_v1_gm-3-flash"]

for t in tags:
    sub = df[df.run_tag == t]
    if sub.empty:
        print(f"\n--- {t}: NOT FOUND ---")
        continue
    n = len(sub)
    overall = sub.correct.mean() * 100
    actions = sub.action.value_counts()
    acc = sub.groupby("action")["correct"].mean().mul(100).round(1)
    print(f"\n--- {t} ---")
    print(f"n={n}, overall={overall:.1f}%")
    print("Action counts:")
    print(actions.to_string())
    print("Accuracy by action:")
    print(acc.to_string())
