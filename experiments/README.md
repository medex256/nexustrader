# Experiments (Evaluation Harness)

This folder is the “report-ready” home for running batch experiments and saving outputs.

## Folder layout

- `inputs/` — text files for tickers/dates lists
- `configs/` — experiment configs (optional JSON) for reproducibility
- `results/raw/` — raw batch outputs (`.jsonl`) **(gitignored)**
- `results/scored/` — scored per-run CSVs and summaries **(gitignored)**
- `results/paper/` — small, curated tables/figures you reference in the FYP report **(tracked)**

## Recommended workflow

1) Run the backend locally (or against a hosted URL)
2) Run batch generation to `results/raw/`
3) Run scoring to `results/scored/`
4) Copy the final tables you want to cite into `results/paper/`

## Example commands (from workspace root)

```powershell
# 1) Generate batch JSONL (writes into nexustrader/experiments/results/raw)
python .\scripts\run_batch.py \
  --tickers-file .\scripts\inputs\tickers.txt \
  --dates-file .\scripts\inputs\dates.txt \
  --horizon short \
  --workers 2 \
  --tag exp_short

# 2) Score (writes into nexustrader/experiments/results/scored)
python .\scripts\score_results.py \
  --input .\nexustrader\experiments\results\raw\batch_exp_short_*.jsonl \
  --hold exclude \
  --tag exp_short_k_auto
```

Notes:
- Use `--horizon short|medium|long` to align generation + scoring.
- Keep `results/raw` and `results/scored` out of git; only commit curated `results/paper` artifacts.
