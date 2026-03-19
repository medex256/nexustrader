import argparse
import json
from collections import Counter

HOLD_EPSILON = 0.02


def true_label_from_return(k_ret: float) -> str:
    if k_ret > HOLD_EPSILON:
        return "BUY"
    if k_ret < -HOLD_EPSILON:
        return "SELL"
    return "HOLD"


def load_dates(path: str) -> set[str]:
    with open(path, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def extract_judgment(result: dict, strategy: dict) -> str:
    """Best-effort risk judgment extraction from compact/full outputs."""
    valid = {"BLOCK", "REDUCE", "CLEAR"}

    # 1) Prefer explicit summary field when available.
    explicit = str(result.get("risk_judgment") or "").strip().upper()
    if explicit in valid:
        return explicit

    # 2) Try compact/full risk gate text.
    risk_obj = result.get("risk") or {}
    risk_gate = str(risk_obj.get("risk_gate") or "")
    if not risk_gate:
        risk_reports = result.get("risk_reports") or {}
        risk_gate = str(risk_reports.get("risk_gate") or "")

    risk_gate_upper = risk_gate.upper()
    for tag in valid:
        if f"JUDGMENT: {tag}" in risk_gate_upper:
            return tag

    # 3) Fall back to strategy rationale tags.
    rationale = str(strategy.get("rationale") or "")
    for tag in ("[BLOCK]", "[REDUCE]", "[CLEAR]"):
        if tag in rationale:
            return tag.strip("[]")

    return "UNKNOWN"


def load_run(path: str, target_dates: set[str] | None = None) -> dict:
    data = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            obj = json.loads(line)
            if "error" in obj:
                continue

            ticker = obj.get("ticker")
            sim_date = obj.get("simulated_date")
            if not ticker or not sim_date:
                continue
            if target_dates and sim_date not in target_dates:
                continue

            # Compact output puts strategy under result.trading_strategy.
            result = obj.get("result", {}) or {}
            st = result.get("trading_strategy", {}) or {}

            action = str(st.get("action") or result.get("action") or "HOLD").strip().upper()
            rationale = str(st.get("rationale") or "")
            pos_size = float(st.get("position_size_pct") or 0.0)

            k_ret = obj.get("k_return")
            if k_ret is None:
                # Fall back to trace style if available.
                k_ret = obj.get("result", {}).get("k_return")
            try:
                k_ret = float(k_ret)
            except Exception:
                k_ret = None

            risk_gate = str((result.get("risk") or {}).get("risk_gate") or "")
            run_cfg = result.get("run_config") or obj.get("flags") or {}

            judgment = extract_judgment(result, st)

            has_truth = k_ret is not None
            key = f"{ticker}_{sim_date}"
            data[key] = {
                "ticker": ticker,
                "simulated_date": sim_date,
                "action": action,
                "k_return": k_ret,
                "true_label": true_label_from_return(k_ret) if has_truth else None,
                "correct": int(action == true_label_from_return(k_ret)) if has_truth else None,
                "has_truth": has_truth,
                "rationale": rationale,
                "judgment": judgment,
                "position_size_pct": pos_size,
                "risk_gate": risk_gate,
                "run_config": run_cfg,
            }

    return data


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {
            "n": 0,
            "overall_acc_%": 0.0,
            "dir_acc_ex_hold_%": 0.0,
            "dir_n": 0,
            "hold_n": 0,
            "hold_rate_%": 0.0,
            "avg_pos_%_non_hold": 0.0,
        }

    eval_rows = [r for r in rows if r.get("has_truth")]
    correct_all = sum(r["correct"] for r in eval_rows)
    hold_n = sum(1 for r in rows if r["action"] == "HOLD")
    directional = [r for r in eval_rows if r["action"] in {"BUY", "SELL"}]
    dir_correct = sum(r["correct"] for r in directional)
    dir_n = len(directional)
    pos = [r["position_size_pct"] for r in rows if r["action"] in {"BUY", "SELL"}]
    eval_n = len(eval_rows)

    return {
        "n": n,
        "eval_n": eval_n,
        "overall_acc_%": round(100.0 * correct_all / eval_n, 2) if eval_n else None,
        "dir_acc_ex_hold_%": round(100.0 * dir_correct / dir_n, 2) if dir_n else 0.0,
        "dir_n": dir_n,
        "hold_n": hold_n,
        "hold_rate_%": round(100.0 * hold_n / n, 2),
        "avg_pos_%_non_hold": round(sum(pos) / len(pos), 4) if pos else 0.0,
    }


def print_summary(label: str, summary: dict, judgments: Counter) -> None:
    print(f"\n=== {label} ===")
    print(f"n={summary['n']}")
    print(f"eval_n={summary['eval_n']}")
    if summary["overall_acc_%"] is None:
        print("overall_acc_%=N/A (k_return not present in these rows)")
        print("dir_acc_ex_hold_%=N/A (k_return not present in these rows)")
    else:
        print(f"overall_acc_%={summary['overall_acc_%']}")
        print(f"dir_acc_ex_hold_%={summary['dir_acc_ex_hold_%']} (dir_n={summary['dir_n']})")
    print(f"hold_n={summary['hold_n']} hold_rate_%={summary['hold_rate_%']}")
    print(f"avg_pos_%_non_hold={summary['avg_pos_%_non_hold']}")
    print(
        "judgments="
        f"BLOCK:{judgments.get('BLOCK', 0)} "
        f"REDUCE:{judgments.get('REDUCE', 0)} "
        f"CLEAR:{judgments.get('CLEAR', 0)} "
        f"UNKNOWN:{judgments.get('UNKNOWN', 0)}"
    )


def compare_pair(base_rows: dict, cmp_rows: dict, base_label: str, cmp_label: str) -> None:
    keys = sorted(set(base_rows) & set(cmp_rows))
    helped = 0
    hurt = 0
    changed = 0

    for k in keys:
        b = base_rows[k]
        c = cmp_rows[k]
        if b["action"] != c["action"]:
            changed += 1
        if b.get("correct") is None or c.get("correct") is None:
            continue
        if b["correct"] == 0 and c["correct"] == 1:
            helped += 1
        elif b["correct"] == 1 and c["correct"] == 0:
            hurt += 1

    print(f"\n--- Flip comparison: {base_label} vs {cmp_label} ---")
    print(f"Matched rows: {len(keys)}")
    print(f"Decision flips: {changed}")
    print(f"Helped ({base_label} wrong -> {cmp_label} right): {helped}")
    print(f"Hurt   ({base_label} right -> {cmp_label} wrong): {hurt}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare B+ / C-R1 / C-R2 on matched rows and risk judgments")
    parser.add_argument("--dates-file", default="inputs/dates_eval50.txt")
    parser.add_argument("--run-bplus", default="results/raw/batch_eval50_stageB_plus_v2_20260318_160511.jsonl")
    parser.add_argument("--label-bplus", default="Stage B+")
    parser.add_argument("--run-c-r1", default="results/raw/batch_eval50_stageC_v2_20260319_194910.jsonl")
    parser.add_argument("--label-c-r1", default="Stage C-R1")
    parser.add_argument("--run-c-r2", default="")
    parser.add_argument("--label-c-r2", default="Stage C-R2")
    args = parser.parse_args()

    target_dates = load_dates(args.dates_file)
    print(f"Loaded {len(target_dates)} target dates from {args.dates_file}")

    runs: list[tuple[str, dict]] = []

    bplus = load_run(args.run_bplus, target_dates)
    runs.append((args.label_bplus, bplus))

    if args.run_c_r1:
        runs.append((args.label_c_r1, load_run(args.run_c_r1, target_dates)))
    if args.run_c_r2:
        runs.append((args.label_c_r2, load_run(args.run_c_r2, target_dates)))

    # Build strict matched universe across all supplied runs
    shared_keys = set(runs[0][1].keys())
    for _, run_data in runs[1:]:
        shared_keys &= set(run_data.keys())

    print(f"Matched rows across provided runs: {len(shared_keys)}")

    filtered_runs: list[tuple[str, dict, dict, Counter]] = []
    for label, run_data in runs:
        rows = [run_data[k] for k in sorted(shared_keys)]
        s = summarize(rows)
        j = Counter(r["judgment"] for r in rows)
        filtered_runs.append((label, {k: run_data[k] for k in shared_keys}, s, j))

    for label, _, s, j in filtered_runs:
        print_summary(label, s, j)

    if len(filtered_runs) >= 2:
        compare_pair(filtered_runs[0][1], filtered_runs[1][1], filtered_runs[0][0], filtered_runs[1][0])
    if len(filtered_runs) >= 3:
        compare_pair(filtered_runs[0][1], filtered_runs[2][1], filtered_runs[0][0], filtered_runs[2][0])
        compare_pair(filtered_runs[1][1], filtered_runs[2][1], filtered_runs[1][0], filtered_runs[2][0])


if __name__ == "__main__":
    main()
