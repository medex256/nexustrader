# Single-Horizon Batch Runner - Quick Reference

## What Changed (Feb 12, 2026)

### 1. Removed Multi-Horizon Complexity
**Before:** `--horizons all` would run short+medium+long in one batch  
**After:** Single `--horizon short|medium|long` per batch (clean i.i.d. design)

**Why?**  
- Clean ablation studies require controlling for horizon
- Multi-horizon mixing confounds memory/debate effects
- FYP benchmark should use **one primary horizon** (recommended: `short` = k=10)

### 2. Persistent Finnhub News Cache
**Before:** 30-min TTL cache → re-fetched every session  
**After:** `ttl_seconds=0` → cached forever within backend session

**Impact:**  
- First run: fetches from Finnhub (60/min limit)
- Subsequent runs: instant (0 API calls)
- Reproducibility: identical news across ablations

### 3. Unified 14-Day News Lookback
**Before:** Horizon-dependent (short=7d, medium=14d, long=30d)  
**After:** Fixed 14-day window for all horizons

**Why?**  
- Removes news-retrieval confound between horizon experiments
- 14 days captures earnings cycles for all horizon types
- Stays within Finnhub 1-year historical window safely

---

## Usage Examples

### Basic Run (Single Horizon)
```bash
python run_batch.py \
  --horizon short \
  --tag baseline_k10 \
  --workers 1
```

### Multiple Horizons (Separate Batches)
```bash
# Primary benchmark: short horizon (k=10)
python run_batch.py --horizon short --tag primary_k10

# Secondary comparison: medium horizon (k=21)
python run_batch.py --horizon medium --tag secondary_k21

# UI/long-term: long horizon (k=126)
python run_batch.py --horizon long --tag longterm_k126
```

### With Memory Ablation
```bash
# Memory off (i.i.d. benchmark)
python run_batch.py --horizon short --memory-off --tag baseline_nomem

# Memory on (sequential experiment)
python run_batch.py --horizon short --memory-on --tag sequential_mem
```

### With Debate Rounds
```bash
# No debate
python run_batch.py --horizon short --debate-rounds 0 --tag nodebate

# Standard debate
python run_batch.py --horizon short --debate-rounds 1 --tag debate1

# Extended debate
python run_batch.py --horizon short --debate-rounds 2 --tag debate2
```

---

## CLI Reference

### Required (uses defaults or files)
- `--tickers-file` (default: `experiments/inputs/tickers.txt`) OR `--tickers AAPL,MSFT`
- `--dates-file` (default: `experiments/inputs/dates.txt`) OR `--dates 2025-03-03,2025-03-17`

### Experiment Configuration
- `--horizon` (`short`|`medium`|`long`) - **Single horizon only**
  - `short` = k=10 days (primary FYP benchmark)
  - `medium` = k=21 days (secondary comparison)
  - `long` = k=126 days (6-month UI feature)
- `--debate-rounds` (`0`|`1`|`2`) - Number of bull/bear debate rounds
- `--memory-on` / `--memory-off` - Enable/disable agent memory (default: `--memory-on`)
- `--risk-on` / `--risk-off` - Enable/disable risk management (default: `--risk-on`)
- `--social-on` / `--social-off` - Enable/disable social sentiment (default: `--social-off`)

### Output Control
- `--tag` - Label for output file (e.g., `baseline`, `debate2`, `mem_off`)
- `--output` (`full`|`compact`) - Result verbosity (default: `compact`)
- `--workers` - Parallel execution (1=sequential, 2-4 recommended; default: 1)

### Advanced
- `--api` - Backend URL (default: `http://127.0.0.1:8000`)
- `--market` - Market code (default: `US`)
- `--truncate-chars` - Truncate rationale text in compact mode (default: 400)

---

## Current Input Files

### Tickers (`experiments/inputs/tickers.txt`)
```
AAPL
NVDA
TSLA
JPM
XOM
```

### Dates (`experiments/inputs/dates.txt`)
```
2025-03-03
2025-03-17
2025-03-31
... (25 dates total, bi-weekly through 2026-02-02)
```

**Total runs per batch:** 5 tickers × 25 dates = **125 runs**

---

## Output Structure

### JSONL Record Format
```json
{
  "ticker": "AAPL",
  "market": "US",
  "simulated_date": "2025-03-03",
  "horizon": "short",
  "flags": {
    "debate_rounds": 1,
    "memory_on": true,
    "risk_on": true,
    "social_on": false
  },
  "result": {
    "trading_strategy": {...},
    "proposed_trade": {...},
    "risk": {...},
    "provenance": {
      "news": {
        "lookback_days": 14,
        "article_count": 23
      }
    }
  }
}
```

### File Naming
```
batch_{tag}_{timestamp}.jsonl

Examples:
  batch_baseline_k10_20260212_143022.jsonl
  batch_debate2_20260212_151045.jsonl
  batch_nomem_20260212_160333.jsonl
```

---

## Typical Workflow

### 1. Start Backend
```bash
cd nexustrader/backend
uvicorn app.main:app --reload
```

### 2. Run Primary Benchmark
```bash
cd nexustrader/experiments/scripts
python run_batch.py --horizon short --tag baseline_k10
```

**First run:** ~2-3 minutes (fetches Finnhub news)  
**Cached runs:** ~30-45 seconds (LLM only)

### 3. Score Results
```bash
cd nexustrader/experiments/scripts
python score_results.py \
  --input ../../results/raw/batch_baseline_k10_*.jsonl \
  --k 10 \
  --hold-mode neutral_band
```

### 4. Run Ablations (Same Cache!)
```bash
# Memory off
python run_batch.py --horizon short --memory-off --tag nomem_k10

# Extended debate
python run_batch.py --horizon short --debate-rounds 2 --tag debate2_k10

# No risk
python run_batch.py --horizon short --risk-off --tag norisk_k10
```

**All ablations use cached news → identical inputs, only mechanism changes**

---

## Troubleshooting

### "No articles returned"
- Check dates are within Finnhub's 1-year window (2025-03 to 2026-02 is safe)
- Verify `FINNHUB_API_KEY` or `FINHUB_API_KEY` in `.env`

### Rate limit errors (429)
- Only occurs on first uncached run
- Use `--workers 1` or `2` to stay under 60/min
- Subsequent runs are instant (cached)

### Backend session reset
- Restarting `uvicorn` clears in-memory cache
- First run after restart will re-fetch news (then cache persists for that session)

### Wrong horizon in output
- Check `--horizon` flag (no more `--horizons`)
- Each batch is single-horizon by design

---

## Design Rationale for FYP

### Why Single-Horizon?
1. **Clean ablations:** Each experiment varies ONE mechanism (debate, memory, risk)
2. **Horizon as control variable:** Run separate batches for k=10, k=21, k=126
3. **Report clarity:** Primary results use one horizon; appendix shows horizon sensitivity

### Why 14-Day Unified Lookback?
1. **Consistency:** Same news window across all horizons
2. **Comparability:** Memory/debate effects not confounded by different news sets
3. **Feasibility:** Fits within Finnhub 1-year window for all 2025-2026 dates

### Why Persistent Cache?
1. **Reproducibility:** Ablations see identical news (critical for fair comparison)
2. **Speed:** 125-run batch takes 30s instead of 3min after first pass
3. **Cost:** 0 API calls on cached runs (vs 125 calls each time)

---

## Recommended FYP Experiment Plan

### Phase 1: Primary Benchmark (k=10)
```bash
# Baseline
python run_batch.py --horizon short --tag baseline

# Debate ablation
python run_batch.py --horizon short --debate-rounds 0 --tag nodebate
python run_batch.py --horizon short --debate-rounds 2 --tag debate2

# Memory ablation
python run_batch.py --horizon short --memory-off --tag nomem

# Risk ablation
python run_batch.py --horizon short --risk-off --tag norisk
```

### Phase 2: Horizon Sensitivity (Appendix)
```bash
python run_batch.py --horizon medium --tag secondary_k21
python run_batch.py --horizon long --tag longterm_k126
```

### Phase 3: Sequential Memory (if time permits)
```bash
# Requires chronological date ordering and memory carryover
python run_batch.py --horizon short --memory-on --tag sequential
```

**Total runtime:** ~5-10 minutes first pass (with Finnhub fetch), then <2 min per ablation (cached)
