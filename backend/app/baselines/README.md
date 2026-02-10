# Non-Agentic Baselines for NexusTrader

This module implements simple, rule-based trading strategies for comparison with NexusTrader's agentic system.

## Available Baselines

### B1: Buy & Hold
- **Strategy**: Always BUY (passive long-only)
- **Use case**: Benchmark for passive market exposure
- **Expected performance**: Tracks underlying asset returns

### B2: SMA Crossover (20/50)
- **Strategy**: BUY when SMA_20 > SMA_50, SELL when SMA_20 < SMA_50
- **Use case**: Classic trend-following baseline
- **Expected performance**: Captures directional trends, lags reversals

### B3: RSI Threshold (30/70)
- **Strategy**: BUY if RSI < 30 (oversold), SELL if RSI > 70 (overbought), else HOLD
- **Use case**: Mean-reversion / contrarian baseline
- **Expected performance**: Captures bounce-backs, may underperform in trending markets

### B4: Random (coinflip)
- **Strategy**: Randomly choose BUY or SELL with 50/50 probability
- **Use case**: Sanity check baseline
- **Expected performance**: ~50% directional accuracy

## Usage

### 1. Test baselines locally
```bash
cd nexustrader/backend
python -m app.test_baselines
```

### 2. Via API endpoint
```bash
# Start backend first
uvicorn app.main:app --reload

# Call baseline endpoint
curl -X POST http://localhost:8000/baseline \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "baseline": "sma",
    "simulated_date": "2024-12-31"
  }'
```

### 3. Quick comparison (all strategies at once)
```bash
python scripts/quick_compare.py AAPL 2024-12-31
```

This runs NexusTrader + all 4 baselines and outputs a comparison table.

## Output Schema

All baselines emit the same schema as NexusTrader for consistent evaluation:

```json
{
  "baseline_name": "SMA_20_50",
  "ticker": "AAPL",
  "simulated_date": "2024-12-31",
  "trading_strategy": {
    "action": "BUY|SELL|HOLD",
    "entry_price": 123.45,
    "take_profit": 129.62,
    "stop_loss": 120.98,
    "position_size_pct": 20,
    "rationale": "SMA_20 (260.15) > SMA_50 (268.70): bullish crossover"
  }
}
```

## For Batch Evaluation

Baselines can be run in batch mode using the same infrastructure as NexusTrader:

```python
from app.baselines.strategies import get_baseline

strategy = get_baseline('sma')
result = strategy.generate_signal('AAPL', '2024-12-31')
```

This allows fair comparison using the same:
- Data sources (yfinance)
- Date cutoffs (simulated_date)
- Scoring logic (k-day forward returns)

## Notes

- All baselines respect `simulated_date` cutoffs (no look-ahead bias)
- Position sizes are fixed per strategy (unlike NexusTrader's adaptive sizing)
- TP/SL levels use simple percentage rules (±2-5%) for comparability
- Random baseline uses fixed seed (42) for reproducibility
