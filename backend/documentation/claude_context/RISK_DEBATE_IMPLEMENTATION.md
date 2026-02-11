# Risk Debate Implementation Summary

**Date:** February 11, 2026  
**Status:** ✅ Complete - Ready for Testing

---

## What Was Implemented

### 1. Three Risk Analyst Agents (`agents/risk_management.py`)

**Aggressive Risk Analyst**
- **Role:** Challenge conservatism, advocate for action
- **Focus:** Opportunity cost, growth potential, "what we lose by doing nothing"
- **Key Feature:** Explicitly challenges HOLD recommendations

**Conservative Risk Analyst**
- **Role:** Protect capital, minimize losses
- **Focus:** Downside risks, volatility, worst-case scenarios
- **Key Feature:** Defends HOLD when appropriate, identifies risks in BUY/SELL

**Neutral Risk Analyst**
- **Role:** Balance risk and reward
- **Focus:** Risk-adjusted returns, optimal position sizing
- **Key Feature:** Evaluates both sides, proposes middle-ground solutions

### 2. Risk Manager as Judge

**Old Behavior (Before):**
- Simple passthrough for HOLD decisions
- Only applied risk gates (position size limits, stop-loss defaults)
- No ability to challenge Strategy Synthesizer's recommendation

**New Behavior (After):**
- **Judge Mode:** Evaluates 3-way risk debate, makes final decision
- Can override Strategy Synthesizer (including changing HOLD → BUY/SELL)
- **Legacy Mode:** Falls back to simple validator if risk debate disabled
- Applies risk gates after final decision

### 3. Graph Routing (`graph/agent_graph.py`)

**New Flow:**
```
Strategy Synthesizer
    ↓
Aggressive Risk Analyst
    ↓
Conservative Risk Analyst
    ↓
Neutral Risk Analyst
    ↓ (loop if max_risk_debate_rounds > 1)
Risk Manager (Judge)
    ↓
END
```

**Conditional Routing (`graph/conditional_logic.py`):**
- `should_continue_risk_debate()` handles loop logic
- Tracks debate rounds (3 exchanges = 1 round)
- Routes: Aggressive → Conservative → Neutral → (repeat or judge)

### 4. State Management (`graph/state.py`)

**Updated RiskDebateState:**
```python
{
    "history": str,                 # Full transcript
    "aggressive_history": str,      # Aggressive analyst's points
    "conservative_history": str,    # Conservative analyst's points
    "neutral_history": str,         # Neutral analyst's points
    "latest_speaker": str,          # Last speaker name
    "count": int,                   # Total exchanges
    "final_decision": str           # Optional final decision
}
```

---

## How to Test

### Quick Test (3 tickers)
```bash
cd nexustrader/backend
python test_risk_debate.py
```

**Expected Output:**
- HOLD rate drops from 75% → <50%
- See debate transcripts in console
- Summary stats at end

### Full Batch Test
```bash
cd nexustrader/experiments
python .\scripts\run_batch.py --tickers-file .\inputs\tickers.txt --dates-file .\inputs\dates.txt --horizons all --debate-rounds 1 --memory-off --risk-on --social-off --workers 6 --tag risk_debate_test
```

Then score:
```bash
python .\scripts\score_results.py .\results\raw\batch_risk_debate_test_*.jsonl --output-dir .\results\scored --tag risk_debate_test
```

---

## Configuration Flags

### Enable/Disable Risk Debate

**Via run_config:**
```python
{
    "risk_on": True,  # Must be True for debate to occur
    # Risk debate always enabled if risk_on=True
    # To disable debate, set risk_on=False (uses legacy validator)
}
```

**Via agent_graph creation:**
```python
graph = create_agent_graph(
    max_debate_rounds=1,        # Bull/Bear debate rounds
    max_risk_debate_rounds=1    # Risk debate rounds (NEW)
)
```

**Default behavior:**
- `max_risk_debate_rounds=1` → 3 exchanges (aggressive, conservative, neutral)
- `max_risk_debate_rounds=2` → 6 exchanges (2 full cycles)

---

## Expected Performance Improvements

Based on TradingAgents paper and our analysis:

| Metric | Before (Baseline) | Target (With Risk Debate) | Impact |
|--------|------------------|---------------------------|--------|
| **HOLD Rate** | 75.5% (290/384) | <50% (<192/384) | -25% HOLD |
| **Coverage** | 24.5% (94/384) | >50% (>192/384) | +25% coverage |
| **Accuracy** | 51.1% | >55% | +4-7% |
| **Mean Return** | +3.23% | >+4.5% | +1.3% |

---

## Architecture Changes

### Agent Count
- **Before:** 9 agents (4 analysts + 3 debate + 1 strategy + 1 risk)
- **After:** 12 agents (4 analysts + 3 debate + 1 strategy + 3 risk + 1 judge)

### Cost Impact
- **Extra calls per run:** +3 risk analysts = 3 LLM calls
- **Cost increase:** $0.38 → $0.54 per 384 runs (+42% but still negligible)
- **With flash-lite:** ~$0.0014 per run
- **With flash:** ~$0.0014 per run (same cost, better quality)

---

## Next Steps

1. **✅ DONE:** Implement risk debate architecture
2. **⏳ TODO:** Run `test_risk_debate.py` to verify it works
3. **⏳ TODO:** If successful, run full 384-run batch with risk debate
4. **⏳ TODO:** Compare before/after results (HOLD rate, accuracy, coverage)
5. **⏳ TODO:** Document findings for FYP report

---

## Key Files Modified

1. `agents/risk_management.py` — Added 3 risk analysts + refactored risk manager
2. `graph/agent_graph.py` — Added risk debate routing
3. `graph/conditional_logic.py` — Added `should_continue_risk_debate()`
4. `graph/state.py` — Updated `RiskDebateState` schema
5. `test_risk_debate.py` — NEW: Test script for validation

---

## Troubleshooting

**If HOLD rate is still high:**
- Check aggressive analyst prompt — should be confrontational
- Increase `max_risk_debate_rounds` to 2 (more debate cycles)
- Review Risk Manager judge prompt — ensure "be decisive" language is strong

**If errors occur:**
- Check LLM response formats (risk manager decision extraction)
- Verify `risk_debate_state` is initialized in all paths
- Check conditional routing logic in `should_continue_risk_debate()`

**If graph loops infinitely:**
- Verify `count` is incrementing in each risk analyst
- Check max rounds condition in `should_continue_risk_debate()`
- Ensure `latest_speaker` is set correctly

---

## Report Writing Notes

### Methodology Section
"To address the HOLD-heavy bias (75.5% HOLD rate), we implemented a 3-way adversarial risk debate mechanism inspired by the TradingAgents paper. Three risk analysts (aggressive, conservative, neutral) debate the strategy recommendation, and a Risk Manager acts as judge to make the final decision. The aggressive analyst explicitly challenges HOLD recommendations by articulating opportunity costs."

### Results Section
"Adding risk debate reduced HOLD rate from 75.5% to X%, increasing coverage from 24.5% to Y%, and improving accuracy from 51.1% to Z%."

### Discussion Section
"The risk debate demonstrates that multi-agent systems require disagreement incentives to avoid groupthink. Simply adding more agents that agree doesn't help — they need opposing objectives (maximize return vs. minimize risk) to produce better decisions."

---

**Implementation Complete. Ready for testing!** 🚀
