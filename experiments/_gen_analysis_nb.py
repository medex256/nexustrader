"""
Script to generate experiment_notebook_analysis.ipynb
Reads frozen pre-scored CSVs; no re-running of scoring code.
Run from nexustrader/experiments/.
"""
import json
from pathlib import Path

NB_PATH = Path(__file__).parent / "experiment_notebook_analysis.ipynb"


def md(source_str, id_):
    lines = [l + "\n" for l in source_str.split("\n")]
    # last line: strip trailing \n added above
    if lines and lines[-1] == "\n":
        lines[-1] = ""
    elif lines:
        lines[-1] = lines[-1].rstrip("\n")
    return {"cell_type": "markdown", "id": id_, "metadata": {}, "source": lines}


def code(source_str, id_):
    lines = [l + "\n" for l in source_str.split("\n")]
    if lines:
        lines[-1] = lines[-1].rstrip("\n")
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": id_,
        "metadata": {},
        "outputs": [],
        "source": lines,
    }


cells = []

# ──────────────────────────────────────────────────────────────────────────────
cells.append(md("""# NexusTrader — Frozen Ablation Analysis Notebook

All data loaded from pre-scored frozen CSVs. No LLM calls or re-scoring required.

**Stages covered:** A (baseline) → B (specialist extraction) → B+ (risk gate) → C (risk debate, negative) → D (memory)
**Eval set:** n=385, k=10 trading days, 5 tickers × 77 dates
**Key metric:** `dir_acc_ex_hold_%` — directional accuracy on committed BUY/SELL calls only""", "00-title"))

# ── 0) Imports ────────────────────────────────────────────────────────────────
cells.append(md("## 0) Imports", "01-md-imports"))
cells.append(code(
    """import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

plt.rcParams.update({
    "figure.dpi": 120,
    "font.size": 11,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
})""",
    "02-imports",
))

# ── 1) Config ─────────────────────────────────────────────────────────────────
cells.append(md("## 1) Config & File Paths", "03-md-config"))
cells.append(code(
    r"""BASE_DIR     = Path(".")   # run notebook from nexustrader/experiments/
REPORTS_DIR = BASE_DIR / "results" / "analysis_reports"
CHART_DIR   = BASE_DIR / "results" / "charts_analysis"
CHART_DIR.mkdir(parents=True, exist_ok=True)

STAGE_DIRS = {
    "Stage A":  REPORTS_DIR / "eval385_stageA_new_v2",
    "Stage B":  REPORTS_DIR / "eval385_stageB_v3",
    "Stage B+": REPORTS_DIR / "eval385_stageB_plus_v3",
    "Stage C":  REPORTS_DIR / "eval385_stageC_PAID_V2_R1_final",
    "Stage D":  REPORTS_DIR / "eval385_stageD_llm_lessons_v1",
}

STAGE_ORDER = ["Stage A", "Stage B", "Stage B+", "Stage C", "Stage D"]

STAGE_COLORS = {
    "Stage A":  "#4C72B0",   # blue
    "Stage B":  "#55A868",   # green
    "Stage B+": "#C44E52",   # red
    "Stage C":  "#8172B2",   # purple — negative result
    "Stage D":  "#CCB974",   # gold
}

HOLD_EPSILON_BASE = 0.02                             # epsilon used in all frozen scorings
EPSILON_SWEEP     = [0.01, 0.02, 0.03, 0.05, 0.08]  # sweep for HOLD quality analysis

print("REPORTS_DIR:", REPORTS_DIR.resolve())
print("CHART_DIR:  ", CHART_DIR.resolve())""",
    "04-config",
))

# ── 2) Load Data ──────────────────────────────────────────────────────────────
cells.append(md("## 2) Load Frozen CSVs", "05-md-load"))
cells.append(code(
    """# ── Agent rows per stage ──────────────────────────────────────────────────
agent_dfs   = {}
summary_dfs = {}

for stage in STAGE_ORDER:
    d = STAGE_DIRS[stage]
    df = pd.read_csv(d / "agent_rows_scored.csv")
    df["stage"] = stage
    agent_dfs[stage]   = df
    summary_dfs[stage] = pd.read_csv(d / "agent_summary.csv")

# ── Baselines ─────────────────────────────────────────────────────────────────
# All stages share the same static baselines; Stage A copy is authoritative
baselines = pd.read_csv(STAGE_DIRS["Stage A"] / "baseline_rows_scored.csv")

# ── Matched-rows & flip files ─────────────────────────────────────────────────
a_vs_b_matched    = pd.read_csv(STAGE_DIRS["Stage B"]  / "stageA_stageB_date_matched_rows.csv")
b_vs_bplus_matched = pd.read_csv(STAGE_DIRS["Stage B+"] / "Stage_B_Stage_Bplus_date_matched_rows.csv")

a_vs_b_flips      = pd.read_csv(STAGE_DIRS["Stage B"]  / "stageA_stageB_flips_all.csv")
b_vs_bplus_flips  = pd.read_csv(STAGE_DIRS["Stage B+"] / "Stage_B_Stage_Bplus_flips_all.csv")

stageC_audit  = pd.read_csv(STAGE_DIRS["Stage C"] / "summary_stageC_flip_audit.csv")
stageC_jdist  = pd.read_csv(STAGE_DIRS["Stage C"] / "summary_stageC_judgment_distribution.csv")
stageC_health = pd.read_csv(STAGE_DIRS["Stage C"] / "summary_stageC_health_flags.csv")

# ── Combined long-format DataFrame ───────────────────────────────────────────
all_agent = pd.concat(agent_dfs.values(), ignore_index=True)
all_agent["stage"] = pd.Categorical(all_agent["stage"], categories=STAGE_ORDER, ordered=True)

print("Loaded agent rows per stage:")
for stage in STAGE_ORDER:
    df = agent_dfs[stage]
    h  = (df["action"] == "HOLD").sum()
    print(f"  {stage:<10}: {len(df)} rows | HOLDs={h} ({h/len(df)*100:.1f}%)")
print(f"\\nBaselines: {len(baselines)} rows | strategies: {baselines['strategy'].unique().tolist()}")""",
    "06-load",
))

# ── 3) Summary metrics table ──────────────────────────────────────────────────
cells.append(md("## 3) All-Stage Summary Metrics", "07-md-summary"))
cells.append(code(
    """# Pull metrics from frozen summary CSVs
COLS = {
    "dir_acc":   "dir_acc_ex_hold_%",
    "hold_rate": "hold_rate_%",
    "hold_acc":  "hold_acc_%",
    "buy_acc":   "buy_acc_%",
    "sell_acc":  "sell_acc_%",
    "dir_n":     "dir_acc_ex_hold_n",
    "hold_n":    "hold_n",
    "buy_n":     "buy_n",
    "sell_n":    "sell_n",
    "n":         "n",
    "mean_excess": "mean_excess_vs_bh_%",
}

summ_rows = []
for stage in STAGE_ORDER:
    row = summary_dfs[stage].iloc[0]
    r = {k: float(row[v]) if v in row else float("nan") for k, v in COLS.items()}
    r["stage"] = stage
    summ_rows.append(r)

summ = pd.DataFrame(summ_rows).set_index("stage")

display_cols = ["dir_acc", "hold_rate", "hold_acc", "buy_acc", "sell_acc", "dir_n", "hold_n", "mean_excess"]
print("=== Frozen Summary Metrics (n=385, k=10) ===")
print(summ[display_cols].round(2).to_string())""",
    "08-summary-table",
))

cells.append(code(
    """fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# ── Chart 1: dir_acc_ex_hold ─────────────────────────────────────────────────
ax = axes[0]
colors = [STAGE_COLORS[s] for s in STAGE_ORDER]
bars = ax.bar(STAGE_ORDER, summ.loc[STAGE_ORDER, "dir_acc"],
              color=colors, edgecolor="white", linewidth=1.5, width=0.6)
ax.axhline(50, color="gray", linestyle="--", linewidth=1.2, label="Chance (50%)")
for b, stage in zip(bars, STAGE_ORDER):
    row = summ.loc[stage]
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.3,
            f"{row['dir_acc']:.1f}%\\nn={row['dir_n']:.0f}",
            ha="center", va="bottom", fontsize=9)
ax.set_ylim(44, 64)
ax.set_title("Directional Accuracy ex-Hold by Stage\\n(frozen eval, n=385, k=10)", fontweight="bold")
ax.set_ylabel("dir_acc_ex_hold_%")
ax.legend(fontsize=9)

# ── Chart 2: hold_rate vs hold_acc ───────────────────────────────────────────
ax2 = axes[1]
x = np.arange(len(STAGE_ORDER))
w = 0.38
b1 = ax2.bar(x - w/2, summ.loc[STAGE_ORDER, "hold_rate"],  width=w, color=colors, alpha=0.85,
             label="Hold Rate", edgecolor="white")
b2 = ax2.bar(x + w/2, summ.loc[STAGE_ORDER, "hold_acc"],   width=w, color=colors, alpha=0.45,
             hatch="//", label="Hold Accuracy (ε=0.02)", edgecolor="white")
ax2.axhline(50, color="gray", linestyle="--", linewidth=1, alpha=0.6)
ax2.set_xticks(x)
ax2.set_xticklabels(STAGE_ORDER, rotation=10)
ax2.set_title("Hold Rate vs Hold Accuracy per Stage\\n(ε=0.02)", fontweight="bold")
ax2.set_ylabel("%")
ax2.legend(fontsize=9)

plt.tight_layout()
plt.savefig(CHART_DIR / "01_all_stages_overview.png", bbox_inches="tight")
plt.show()""",
    "09-summary-chart",
))

# ── 4) Baseline Comparisons ───────────────────────────────────────────────────
cells.append(md("""## 4) Baseline Comparisons

Four static baselines (computed once against the same eval rows):
- **buy_hold** — always BUY
- **sma_crossover** — signal from 10/30-day MA cross
- **rsi_14** — RSI < 30 → BUY, > 70 → SELL, else HOLD-equivalent
- **random_uniform** — random BUY/SELL at equal probability

All baselines are committed calls (no HOLD), so their `dir_acc = overall_acc`.""", "10-md-baselines"))
cells.append(code(
    """bl_summ = (
    baselines.groupby("strategy")
    .agg(n=("correct", "count"), overall_acc=("correct", lambda x: round(x.mean() * 100, 2)))
    .reset_index()
).sort_values("overall_acc", ascending=False)

print("Baseline accuracy (all committed, k=10, n per strategy):")
print(bl_summ.to_string(index=False))""",
    "11-baselines-table",
))
cells.append(code(
    """fig, ax = plt.subplots(figsize=(12, 5))

# Agent stages bars
stage_accs = summ.loc[STAGE_ORDER, "dir_acc"].values
bars = ax.bar(STAGE_ORDER, stage_accs,
              color=[STAGE_COLORS[s] for s in STAGE_ORDER],
              width=0.6, edgecolor="white", linewidth=1.5, zorder=3)
for b, val in zip(bars, stage_accs):
    ax.text(b.get_x() + b.get_width() / 2, val + 0.3, f"{val:.1f}%",
            ha="center", va="bottom", fontsize=9)

# Baseline reference lines
bl_style = {
    "buy_hold":       ("#2ca02c", "-"),
    "sma_crossover":  ("#ff7f0e", "--"),
    "rsi_14":         ("#d62728", "-."),
    "random_uniform": ("#9467bd", ":"),
}
for _, row in bl_summ.iterrows():
    strat = row["strategy"]
    clr, ls = bl_style.get(strat, ("gray", "--"))
    ax.axhline(row["overall_acc"], color=clr, linestyle=ls, linewidth=1.8, alpha=0.85,
               label=f"{strat} ({row['overall_acc']:.1f}%)")

ax.axhline(50, color="black", linestyle=":", linewidth=1, alpha=0.35)
ax.set_ylim(40, 68)
ax.set_title("Agent Stages vs Baselines — Directional Accuracy ex-Hold\\n(n=385, k=10)", fontweight="bold")
ax.set_ylabel("Accuracy %")
ax.legend(fontsize=9, loc="upper right")
plt.tight_layout()
plt.savefig(CHART_DIR / "02_baselines_vs_agents.png", bbox_inches="tight")
plt.show()""",
    "12-baselines-chart",
))

# ── 5) Variable Hold Epsilon ──────────────────────────────────────────────────
cells.append(md("""## 5) Variable Hold Epsilon Analysis

The frozen scoring used `HOLD_EPSILON = 0.02` (|k_return| < 2% over k=10 days = "stock barely moved, HOLD correct").

This section re-scores hold quality across different epsilon values to answer:
- Were the stages' HOLD calls _genuinely_ low-volatility calls, or did they abstain on high-movers?
- At what epsilon does a stage's hold accuracy exceed chance?

> Note: `dir_acc_ex_hold` does **not** change with epsilon — it only affects how we evaluate HOLD rows.""", "13-md-epsilon"))
cells.append(code(
    """def metrics_at_epsilon(df, epsilon):
    \"\"\"Recompute HOLD quality at a given epsilon threshold.\"\"\"
    hold_df   = df[df["action"] == "HOLD"]
    commit_df = df[df["action"] != "HOLD"]
    hold_acc = (hold_df["k_return"].abs() < epsilon).mean() * 100 if len(hold_df) > 0 else float("nan")
    dir_acc  = commit_df["correct"].mean() * 100 if len(commit_df) > 0 else float("nan")
    # How many committed rows SHOULD have been held at this epsilon
    missed_hold = int((commit_df["k_return"].abs() < epsilon).sum())
    return {
        "hold_acc":     hold_acc,
        "dir_acc":      dir_acc,
        "hold_rate":    len(hold_df) / len(df) * 100,
        "hold_n":       len(hold_df),
        "dir_n":        len(commit_df),
        "missed_holds": missed_hold,   # committed rows that moved < epsilon
    }

eps_rows = []
for eps in EPSILON_SWEEP:
    for stage in STAGE_ORDER:
        m = metrics_at_epsilon(agent_dfs[stage], eps)
        eps_rows.append({"stage": stage, "epsilon": eps, **m})

eps_df = pd.DataFrame(eps_rows)

print("=== Hold Accuracy (%) at Different Epsilons ===")
pivot = eps_df.pivot_table(index="stage", columns="epsilon", values="hold_acc")
print(pivot.reindex(STAGE_ORDER).round(1).to_string())

print("\\n=== Missed HOLD Opportunities (committed rows with |k_return| < ε) ===")
pivot2 = eps_df.pivot_table(index="stage", columns="epsilon", values="missed_holds")
print(pivot2.reindex(STAGE_ORDER).to_string())""",
    "14-epsilon-compute",
))
cells.append(code(
    """fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Chart 1: Hold accuracy vs epsilon
ax1 = axes[0]
for stage in STAGE_ORDER:
    sub = eps_df[eps_df["stage"] == stage]
    ax1.plot(sub["epsilon"], sub["hold_acc"], marker="o", label=stage,
             color=STAGE_COLORS[stage], linewidth=2, markersize=6)
ax1.axhline(50, color="gray", linestyle="--", linewidth=1.2, alpha=0.7, label="50% reference")
ax1.set_xlabel("Hold Epsilon (|k_return| threshold)")
ax1.set_ylabel("Hold Accuracy %")
ax1.set_title("Hold Accuracy vs Epsilon Threshold\\n(% of HOLD calls where stock barely moved)", fontweight="bold")
ax1.legend(fontsize=9)
ax1.set_xticks(EPSILON_SWEEP)

# Chart 2: Missed holds (committed calls that moved < epsilon)
ax2 = axes[1]
for stage in STAGE_ORDER:
    sub = eps_df[eps_df["stage"] == stage]
    ax2.plot(sub["epsilon"], sub["missed_holds"], marker="^", linestyle="--", label=stage,
             color=STAGE_COLORS[stage], linewidth=1.5)
ax2.set_xlabel("Epsilon")
ax2.set_ylabel("Count")
ax2.set_title("Committed Calls that 'Should Have Been Held'\\n(|k_return| < ε among BUY+SELL rows)", fontweight="bold")
ax2.legend(fontsize=9)
ax2.set_xticks(EPSILON_SWEEP)

plt.tight_layout()
plt.savefig(CHART_DIR / "03_epsilon_sweep.png", bbox_inches="tight")
plt.show()""",
    "15-epsilon-chart",
))

# ── 6) A → B ──────────────────────────────────────────────────────────────────
cells.append(md("""## 6) Stage A → B: Specialist Extraction Impact

Stage B adds two specialist extractors (Upside Catalyst + Downside Risk analysts) whose highlights
the Manager reads before deciding. Stage A Manager reads the analyst reports directly.

Both stages use the **same frozen analyst reports** (cached from Stage A trace).
Disagreements between A and B are therefore attributable to: (1) the additional highlights, and
(2) downstream Manager non-determinism from running on a different day (2026-03-14 vs 2026-03-13).

The flip analysis measures: when Stage B *changed* Stage A's decision, was that change correct?""", "16-md-a-b"))
cells.append(code(
    """flip_rate = a_vs_b_matched["flipped"].mean() * 100
agree_rate = 100 - flip_rate

helped  = int(a_vs_b_flips["flip_helped"].sum())
hurt    = int(a_vs_b_flips["flip_hurt"].sum())
total_f = len(a_vs_b_flips)
neutral = total_f - helped - hurt

print(f"Stage A vs Stage B — {len(a_vs_b_matched)} matched rows")
print(f"  Agreement rate: {agree_rate:.1f}%  |  Flip rate: {flip_rate:.1f}%")
print(f"  Total flips:  {total_f}")
print(f"  Helped (A wrong → B right): {helped}")
print(f"  Hurt   (A right → B wrong): {hurt}")
print(f"  Neutral (both same outcome): {neutral}")
print(f"  Net quality:   {helped - hurt:+d}")

# Action distribution comparison
ab_melted = a_vs_b_matched.melt(
    id_vars=["ticker","simulated_date"],
    value_vars=["action_A", "action_B"], var_name="run", value_name="action"
)
action_dist_ab = ab_melted.groupby(["run","action"]).size().unstack(fill_value=0)
print("\\nAction distribution:")
print(action_dist_ab.to_string())""",
    "17-a-b-stats",
))
cells.append(code(
    """fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# Flip quality bar
ax1 = axes[0]
cats   = ["Helped", "Hurt", "Neutral"]
vals   = [helped, hurt, neutral]
clrs   = ["#55A868", "#C44E52", "#aaaaaa"]
bars   = ax1.bar(cats, vals, color=clrs, edgecolor="white", linewidth=1.5)
for b, v in zip(bars, vals):
    ax1.text(b.get_x() + b.get_width()/2, v + 0.4, str(v), ha="center", fontweight="bold")
ax1.set_title(f"Stage A → B Flip Quality\\n(flips={total_f}, net={helped-hurt:+d})", fontweight="bold")
ax1.set_ylabel("Count")

# Action distribution
ax2 = axes[1]
labels_act = [l for l in ["BUY", "SELL", "HOLD"] if l in action_dist_ab.columns]
x_pos  = np.arange(len(labels_act))
w      = 0.35
a_vals = [action_dist_ab.loc["action_A", l] if l in action_dist_ab.columns else 0 for l in labels_act]
b_vals = [action_dist_ab.loc["action_B", l] if l in action_dist_ab.columns else 0 for l in labels_act]
ax2.bar(x_pos - w/2, a_vals, width=w, label="Stage A", color=STAGE_COLORS["Stage A"], edgecolor="white")
ax2.bar(x_pos + w/2, b_vals, width=w, label="Stage B", color=STAGE_COLORS["Stage B"], edgecolor="white")
ax2.set_xticks(x_pos); ax2.set_xticklabels(labels_act)
ax2.set_title("Action Mix: Stage A vs Stage B", fontweight="bold")
ax2.set_ylabel("Count"); ax2.legend()

plt.tight_layout()
plt.savefig(CHART_DIR / "04_a_vs_b_flips.png", bbox_inches="tight")
plt.show()""",
    "18-a-b-chart",
))

# ── 7) B → B+ ─────────────────────────────────────────────────────────────────
cells.append(md("""## 7) Stage B → B+: Single Risk Gate Impact

Stage B+ adds a single risk judge that can output CLEAR / REDUCE / BLOCK.
BLOCK converts a BUY/SELL to HOLD. REDUCE is a soft caution (no action change in these runs).

Upstream analyst reports and Stage A prior are identical to Stage B.
The Manager call is a **fresh LLM sample** (2026-03-18 vs 2026-03-14) — some disagreements
between B and B+ come from this Manager re-sampling, not from the risk gate directly.
The flip analysis characterises the overall decision quality change.""", "19-md-b-bplus"))
cells.append(code(
    """flip_rate_bb = b_vs_bplus_matched["flipped"].mean() * 100
agree_rate_bb = 100 - flip_rate_bb

# Column names in this file use "Stage B" and "Stage B+"
col_a = "action_Stage B"
col_b = "action_Stage B+"
helped_bb  = int(b_vs_bplus_flips["flip_helped"].sum())
hurt_bb    = int(b_vs_bplus_flips["flip_hurt"].sum())
total_f_bb = len(b_vs_bplus_flips)
neutral_bb = total_f_bb - helped_bb - hurt_bb

print(f"Stage B vs Stage B+ — {len(b_vs_bplus_matched)} matched rows")
print(f"  Agreement rate: {agree_rate_bb:.1f}%  |  Flip rate: {flip_rate_bb:.1f}%")
print(f"  Total flips:  {total_f_bb}")
print(f"  Helped (B wrong → B+ right): {helped_bb}")
print(f"  Hurt   (B right → B+ wrong): {hurt_bb}")
print(f"  Neutral (both same outcome): {neutral_bb}")
print(f"  Net quality:   {helped_bb - hurt_bb:+d}")

bb_melted = b_vs_bplus_matched.melt(
    id_vars=["ticker","simulated_date"],
    value_vars=[col_a, col_b], var_name="run", value_name="action"
)
action_dist_bb = bb_melted.groupby(["run","action"]).size().unstack(fill_value=0)
print("\\nAction distribution:")
print(action_dist_bb.to_string())""",
    "20-b-bplus-stats",
))
cells.append(code(
    """fig, axes = plt.subplots(1, 2, figsize=(13, 5))

ax1 = axes[0]
vals_bb = [helped_bb, hurt_bb, neutral_bb]
bars = ax1.bar(["Helped", "Hurt", "Neutral"], vals_bb, color=["#55A868","#C44E52","#aaaaaa"],
               edgecolor="white", linewidth=1.5)
for b, v in zip(bars, vals_bb):
    ax1.text(b.get_x() + b.get_width()/2, v + 0.4, str(v), ha="center", fontweight="bold")
ax1.set_title(f"Stage B → B+ Flip Quality\\n(flips={total_f_bb}, net={helped_bb-hurt_bb:+d})", fontweight="bold")
ax1.set_ylabel("Count")

ax2 = axes[1]
labels_act = [l for l in ["BUY","SELL","HOLD"] if l in action_dist_bb.columns]
x_pos = np.arange(len(labels_act)); w = 0.35
b_vals2  = [action_dist_bb.loc[col_a, l] if l in action_dist_bb.columns else 0 for l in labels_act]
bp_vals2 = [action_dist_bb.loc[col_b, l] if l in action_dist_bb.columns else 0 for l in labels_act]
ax2.bar(x_pos - w/2, b_vals2,  width=w, label="Stage B",  color=STAGE_COLORS["Stage B"],  edgecolor="white")
ax2.bar(x_pos + w/2, bp_vals2, width=w, label="Stage B+", color=STAGE_COLORS["Stage B+"], edgecolor="white")
ax2.set_xticks(x_pos); ax2.set_xticklabels(labels_act)
ax2.set_title("Action Mix: Stage B vs Stage B+", fontweight="bold")
ax2.set_ylabel("Count"); ax2.legend()

plt.tight_layout()
plt.savefig(CHART_DIR / "05_b_vs_bplus_flips.png", bbox_inches="tight")
plt.show()""",
    "21-b-bplus-chart",
))

# ── 8) B+ → C ─────────────────────────────────────────────────────────────────
cells.append(md("""## 8) Stage B+ → C: Risk Committee (3-Way Debate) Impact

Stage C replaces the single risk judge with a 3-way adversarial debate
(Aggressive + Conservative + Neutral advocates → Judge ruling).

**Primary freeze evidence** is within-Stage-C BLOCK quality (immune to cross-run noise):
- 35 BLOCK rows evaluated against Stage C's own Manager call + ground truth
- Net quality = (helped − hurt) — no B+ comparison needed

The cross-run comparison (B+ vs C accuracy numbers) is provided as context only.
Confidence intervals fully overlap and the gap is attributable to the different run days.""", "22-md-c"))
cells.append(code(
    """# Filter to Stage C-R1 (primary run)
is_c1 = stageC_jdist["run"].str.contains("Stage C-R1", na=False) & \
        ~stageC_jdist["run"].str.contains("malformed|B\\+", na=False)
c1_jdist = stageC_jdist[is_c1].iloc[0]

print("=== Stage C Risk Judgment Distribution (n=385) ===")
print(f"  BLOCK:   {c1_jdist['BLOCK_n']:>4.0f}  ({c1_jdist['BLOCK_%']:.1f}%)")
print(f"  REDUCE:  {c1_jdist['REDUCE_n']:>4.0f}  ({c1_jdist['REDUCE_%']:.1f}%)")
print(f"  CLEAR:   {c1_jdist['CLEAR_n']:>4.0f}  ({c1_jdist['CLEAR_%']:.1f}%)")

# Within-run BLOCK quality (primary evidence — from frozen_progress Section 7)
# 35 BLOCK rows scored against Stage C's own Manager + ground truth
BLOCK_WITHIN = {"helped": 6, "hurt": 11, "neutral": 18, "total": 35}
print(f"\\n=== Within-Run BLOCK Quality (35 BLOCK rows scored within Stage C) ===")
print(f"  Helped  (debate blocked a wrong Manager call): {BLOCK_WITHIN['helped']}")
print(f"  Hurt    (debate blocked a correct Manager call): {BLOCK_WITHIN['hurt']}")
print(f"  Neutral (blocked a HOLD-equivalent call):      {BLOCK_WITHIN['neutral']}")
print(f"  Net:    {BLOCK_WITHIN['helped'] - BLOCK_WITHIN['hurt']:+d}  ← primary freeze basis")

# Cross-run flip audit (supplementary — compare to B+ frozen run)
print("\\n=== Cross-Run Flip Audit vs B+ (supplementary — noisy cross-run comparison) ===")
is_c1_audit = stageC_audit["run"].str.contains("Stage C-R1", na=False) & \
              ~stageC_audit["run"].str.contains("malformed|B\\+", na=False)
print(stageC_audit[is_c1_audit][["risk_judgment","flips","helped","hurt","neutral","net_help_minus_hurt"]].to_string(index=False))""",
    "23-c-stats",
))
cells.append(code(
    """fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# Judgment distribution pie
ax1 = axes[0]
judgment_labels = [f"CLEAR\\n{c1_jdist['CLEAR_%']:.0f}%",
                   f"REDUCE\\n{c1_jdist['REDUCE_%']:.0f}%",
                   f"BLOCK\\n{c1_jdist['BLOCK_%']:.0f}%"]
judgment_vals   = [c1_jdist["CLEAR_n"], c1_jdist["REDUCE_n"], c1_jdist["BLOCK_n"]]
judgment_colors = ["#55A868", "#CCB974", "#C44E52"]
wedges, texts   = ax1.pie(judgment_vals, labels=judgment_labels, colors=judgment_colors,
                           startangle=90, wedgeprops={"edgecolor":"white","linewidth":1.5})
ax1.set_title(f"Stage C Risk Judgment Distribution\\n(n=385 rows)", fontweight="bold")

# Within-run BLOCK quality
ax2 = axes[1]
blk_cats = ["Helped", "Hurt", "Neutral"]
blk_vals = [BLOCK_WITHIN["helped"], BLOCK_WITHIN["hurt"], BLOCK_WITHIN["neutral"]]
blk_clrs = ["#55A868", "#C44E52", "#aaaaaa"]
bars     = ax2.bar(blk_cats, blk_vals, color=blk_clrs, edgecolor="white", linewidth=1.5)
for b, v in zip(bars, blk_vals):
    ax2.text(b.get_x() + b.get_width()/2, v + 0.2, str(v), ha="center", fontweight="bold")
ax2.set_title(f"Stage C: BLOCK Quality (within-run, n=35)\\nNet = {BLOCK_WITHIN['helped']-BLOCK_WITHIN['hurt']:+d}",
              fontweight="bold")
ax2.set_ylabel("Count")
ax2.set_ylim(0, 25)

plt.tight_layout()
plt.savefig(CHART_DIR / "06_stageC_risk_committee.png", bbox_inches="tight")
plt.show()""",
    "24-c-chart",
))

# ── 9) C → D ──────────────────────────────────────────────────────────────────
cells.append(md("""## 9) Stage C → D: Memory Layer Impact

Stage D = Stage B+ topology + `memory_on=True` (ChromaDB read-only queries with prior lessons).
Run date: 2026-03-21 (same day as Stage C, different worker group).

Since Stage D and Stage C share the same topology minus the risk-debate committee (D uses single risk gate like B+),
the fairest comparison is **D vs B** and **D vs B+** (same topology as D baseline).

Stage C is not a clean comparison for D because they differ in two mechanisms (memory AND debate removal).
The D vs C diff collapses both simultaneously.""", "25-md-d"))
cells.append(code(
    """# Compare D, B, B+ action distributions
fig, ax = plt.subplots(figsize=(10, 5))

compare_stages = ["Stage B", "Stage B+", "Stage D"]
x = np.arange(3)  # BUY, SELL, HOLD

for i, stage in enumerate(compare_stages):
    df  = agent_dfs[stage]
    buy  = (df["action"] == "BUY").sum()
    sell = (df["action"] == "SELL").sum()
    hold = (df["action"] == "HOLD").sum()
    w    = 0.25
    bars = ax.bar([j + (i - 1) * w for j in x], [buy, sell, hold],
                  width=w, label=stage, color=STAGE_COLORS[stage], edgecolor="white")

ax.set_xticks(x)
ax.set_xticklabels(["BUY", "SELL", "HOLD"])
ax.set_title("Action Distribution: B vs B+ vs D\\n(n=385 each)", fontweight="bold")
ax.set_ylabel("Count")
ax.legend()
plt.tight_layout()
plt.savefig(CHART_DIR / "07_d_vs_b_action_dist.png", bbox_inches="tight")
plt.show()

# D vs B accuracy comparison from summary
print("=== D vs B comparison (same topology, different run days) ===")
for stage in ["Stage B", "Stage B+", "Stage D"]:
    r = summ.loc[stage]
    print(f"  {stage:<10}: dir_acc={r['dir_acc']:.2f}%  hold_rate={r['hold_rate']:.2f}%  dir_n={r['dir_n']:.0f}")

# Cross-merge D and B actions
d_agent = agent_dfs["Stage D"][["ticker","simulated_date","action","correct"]].rename(
    columns={"action":"action_D","correct":"correct_D"})
b_agent = agent_dfs["Stage B"][["ticker","simulated_date","action","correct"]].rename(
    columns={"action":"action_B","correct":"correct_B"})
d_vs_b = pd.merge(b_agent, d_agent, on=["ticker","simulated_date"])
agree_d_b = (d_vs_b["action_B"] == d_vs_b["action_D"]).mean() * 100
print(f"\\nD vs B agreement rate on same rows: {agree_d_b:.1f}%  ({100-agree_d_b:.1f}% differ)")""",
    "26-d-compare",
))

# ── 10) LLM Non-Determinism Fingerprint ───────────────────────────────────────
cells.append(md("""## 10) LLM Non-Determinism Fingerprint

**Key question**: How much of the cross-stage decision variation is LLM noise vs mechanism effect?

**Method**: Stage A actions are fully deterministic (frozen run).
All other stages used cached Stage A analyst reports as upstream input.
Any disagreement between Stage A and Stage X on the same row = downstream LLM variation
(Manager non-determinism + mechanism effect combined).

**Pairings:**
- A vs B, A vs B+, A vs C, A vs D — all used same cached Stage A inputs upstream
- B vs D — same topology (B+ single-gate), run 7 days apart: pure LLM noise estimate

The within-pairings flip quality (helped/hurt) characterises whether disagreements are informative.
If helped ≈ hurt, the disagreements are dominated by noise, not mechanism effect.""", "27-md-llm-noise"))
cells.append(code(
    """# We have matched rows (all 385) for A vs B and B vs B+
# For other pairs, merge agent_rows manually

def pairwise_agree(df_x, df_y, label_x, label_y):
    \"\"\"Merge two stage DataFrames and compute agreement/flip stats.\"\"\"
    x = df_x[["ticker","simulated_date","action","correct"]].rename(
        columns={"action": f"action_{label_x}", "correct": f"correct_{label_x}"})
    y = df_y[["ticker","simulated_date","action","correct"]].rename(
        columns={"action": f"action_{label_y}", "correct": f"correct_{label_y}"})
    merged = pd.merge(x, y, on=["ticker","simulated_date"])
    agree  = (merged[f"action_{label_x}"] == merged[f"action_{label_y}"]).mean() * 100
    n_flip = (merged[f"action_{label_x}"] != merged[f"action_{label_y}"]).sum()
    flips  = merged[merged[f"action_{label_x}"] != merged[f"action_{label_y}"]]
    # flip quality: when they disagreed, who was right?
    helped = int(((flips[f"correct_{label_x}"] == 0) & (flips[f"correct_{label_y}"] == 1)).sum())
    hurt   = int(((flips[f"correct_{label_x}"] == 1) & (flips[f"correct_{label_y}"] == 0)).sum())
    return {"pair": f"{label_x} vs {label_y}", "n_matched": len(merged),
            "agree_%": round(agree, 1), "n_flips": n_flip,
            "flip_helped": helped, "flip_hurt": hurt, "net": helped - hurt}

noise_rows = []

# A vs B  — use matched rows file for accuracy (has conf)
r = pairwise_agree(agent_dfs["Stage A"], agent_dfs["Stage B"], "A", "B")
noise_rows.append({**r, "run_day_gap": "1 day (2026-03-13 vs -03-14)", "note": "specialist extraction added"})

# A vs B+
r = pairwise_agree(agent_dfs["Stage A"], agent_dfs["Stage B+"], "A", "B+")
noise_rows.append({**r, "run_day_gap": "5 days (2026-03-13 vs -03-18)", "note": "+risk gate added"})

# A vs C
r = pairwise_agree(agent_dfs["Stage A"], agent_dfs["Stage C"], "A", "C")
noise_rows.append({**r, "run_day_gap": "8 days (2026-03-13 vs -03-21)", "note": "+risk debate added"})

# A vs D
r = pairwise_agree(agent_dfs["Stage A"], agent_dfs["Stage D"], "A", "D")
noise_rows.append({**r, "run_day_gap": "8 days (2026-03-13 vs -03-21)", "note": "+memory added"})

# B vs D — same topology (B+ risk gate), 7 days apart: best noise-only estimate
r = pairwise_agree(agent_dfs["Stage B"], agent_dfs["Stage D"], "B", "D")
noise_rows.append({**r, "run_day_gap": "7 days (2026-03-14 vs -03-21)", "note": "same topology (B+ gate), memory differs"})

# C vs D — same day (2026-03-21): minimal noise, differs in risk-debate vs single-gate
r = pairwise_agree(agent_dfs["Stage C"], agent_dfs["Stage D"], "C", "D")
noise_rows.append({**r, "run_day_gap": "0 days (both 2026-03-21)", "note": "risk debate vs single gate"})

noise_df = pd.DataFrame(noise_rows)
print(noise_df[["pair","n_matched","agree_%","n_flips","flip_helped","flip_hurt","net","run_day_gap","note"]].to_string(index=False))""",
    "28-noise-compute",
))
cells.append(code(
    """fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Agreement rates bar chart
ax1 = axes[0]
pair_labels = noise_df["pair"].tolist()
agree_vals  = noise_df["agree_%"].tolist()
bar_colors  = ["#4C72B0","#4C72B0","#4C72B0","#4C72B0","#55A868","#8172B2"]
bars = ax1.bar(pair_labels, agree_vals, color=bar_colors, edgecolor="white", linewidth=1.2, width=0.6)
ax1.axhline(100, color="gray", linestyle=":", linewidth=1, alpha=0.5)
for b, v in zip(bars, agree_vals):
    ax1.text(b.get_x() + b.get_width()/2, v - 1.5, f"{v:.0f}%",
             ha="center", va="top", fontsize=9, color="white", fontweight="bold")
ax1.set_ylim(50, 101)
ax1.set_ylabel("Agreement Rate %")
ax1.set_title("Cross-Stage Action Agreement\\n(same 385 rows; lower = more divergence)", fontweight="bold")
ax1.tick_params(axis="x", rotation=25)

# Flip quality net scores
ax2 = axes[1]
net_vals = noise_df["net"].tolist()
net_clrs = ["#55A868" if v >= 0 else "#C44E52" for v in net_vals]
bars2 = ax2.bar(pair_labels, net_vals, color=net_clrs, edgecolor="white", linewidth=1.2, width=0.6)
ax2.axhline(0, color="black", linewidth=1.2)
for b, v in zip(bars2, net_vals):
    ypos = v + 0.3 if v >= 0 else v - 1.5
    ax2.text(b.get_x() + b.get_width()/2, ypos, f"{v:+d}",
             ha="center", va="bottom", fontsize=9, fontweight="bold")
ax2.set_ylabel("Net Flip Quality (helped − hurt)")
ax2.set_title("Flip Quality per Stage Transition\\n(positive = transition improved decisions)", fontweight="bold")
ax2.tick_params(axis="x", rotation=25)

plt.tight_layout()
plt.savefig(CHART_DIR / "08_llm_nondeterminism.png", bbox_inches="tight")
plt.show()

print("\\nInterpretation guide:")
print("  B vs D agree_%: best estimate of pure LLM noise floor (same topology, different day)")
print("  C vs D agree_%: mechanism signal (mechanism differs, same run day = minimal noise)")""",
    "29-noise-chart",
))

# ── 11) Summary Table ─────────────────────────────────────────────────────────
cells.append(md("""## 11) Full Results Summary Table

Single table for report / presentation use.
Cross-run accuracy numbers are indicative only (LLM non-determinism across run days).""", "30-md-summary-final"))
cells.append(code(
    """from IPython.display import display

report_cols = ["dir_acc", "hold_rate", "hold_acc", "buy_acc", "sell_acc", "dir_n", "hold_n", "mean_excess"]
report = summ[report_cols].copy()
report.columns = ["dir_acc_%", "hold_rate_%", "hold_acc_%", "buy_acc_%", "sell_acc_%",
                  "dir_n", "hold_n", "mean_excess_vs_bh_%"]
report = report.round(2)

print("=== NexusTrader Frozen Ablation Results (n=385, k=10) ===")
display(report)

print("\\n=== Baselines ===")
display(bl_summ.set_index("strategy"))

print("\\n=== Stage C BLOCK Quality (primary freeze evidence) ===")
print(f"  35 BLOCK rows scored within Stage C's own run (independent of B+ comparison)")
print(f"  Helped: {BLOCK_WITHIN['helped']}  Hurt: {BLOCK_WITHIN['hurt']}  "
      f"Neutral: {BLOCK_WITHIN['neutral']}  Net: {BLOCK_WITHIN['helped']-BLOCK_WITHIN['hurt']:+d}")""",
    "31-summary-final",
))

# ──────────────────────────────────────────────────────────────────────────────
nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.10.0",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Notebook written → {NB_PATH}")
print(f"  Cells: {len(cells)}")
