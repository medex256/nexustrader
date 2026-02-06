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
python .\nexustrader\experiments\scripts\run_batch.py \
  --tickers-file .\nexustrader\experiments\inputs\tickers.txt \
  --dates-file .\nexustrader\experiments\inputs\dates.txt \
  --horizon short \
  --workers 2 \
  --tag exp_short

# 2) Score (writes into nexustrader/experiments/results/scored)
python .\nexustrader\experiments\scripts\score_results.py \
  --input .\nexustrader\experiments\results\raw\batch_exp_short_*.jsonl \
  --hold exclude \
  --tag exp_short_k_auto
```

## Run short+medium+long in one command

```powershell
python .\nexustrader\experiments\scripts\run_batch.py \
  --tickers-file .\nexustrader\experiments\inputs\tickers.txt \
  --dates-file .\nexustrader\experiments\inputs\dates.txt \
  --horizons all \
  --workers 2 \
  --tag exp_all_horizons
```

Notes:
- Use `--horizon short|medium|long` to align generation + scoring.
- Keep `results/raw` and `results/scored` out of git; only commit curated `results/paper` artifacts.

## HOLD scoring (recommended)

For report-quality evaluation, consider neutral-band HOLD scoring:

```powershell
python .\nexustrader\experiments\scripts\score_results.py \
  --input .\nexustrader\experiments\results\raw\batch_exp_short_*.jsonl \
  --hold neutral-band \
  --epsilon 0.01 \
  --tag exp_short_hold_band
```

Interpretation: with `--epsilon 0.01`, a HOLD is considered correct if the k-day forward return magnitude is < 1%.
