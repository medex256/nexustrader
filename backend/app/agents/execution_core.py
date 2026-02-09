# In nexustrader/backend/app/agents/execution_core.py

"""
Execution Core Agents

This module contains agents responsible for converting research insights 
into actionable trading strategies.

Active Agents:
- Trading Strategy Synthesizer: Converts research manager's decision into 
  structured trading plan (entry, exit, stop-loss, position size)

Removed Agents (Redundant):
- Arbitrage Trader: Required complex options data not available
- Value Trader: Duplicated Fundamental Analyst's work (95% overlap)
- Bull Trader: Duplicated Bull Researcher's perspective (90% overlap)

See documentation/claude_context/WHY_TRADERS_REDUNDANT.md for details.
"""

from ..llm import invoke_llm as call_llm
from typing import Optional, Literal
from pydantic import BaseModel, Field, ValidationError
from ..tools.portfolio_tools import calculate_ticker_risk_metrics

class TradingStrategy(BaseModel):
    action: Literal["BUY", "SELL", "HOLD"]
    entry_price: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    position_size_pct: Optional[float] = Field(default=0, ge=0, le=100)
    rationale: str


def _extract_json_from_text(text: str) -> str:
    """Extract the first JSON object from a model response."""
    cleaned = text.strip()
    # Remove common code fence wrappers
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")
    return cleaned[start:end + 1]


def trading_strategy_synthesizer_agent(state: dict):
    """
    The Trading Strategy Synthesizer Agent.
    Now uses the investment_plan from the Research Manager.
    """
    # Get the investment plan from research manager
    investment_plan = state.get('investment_plan', '')
    ticker = state.get('ticker', 'Unknown')
    horizon = state.get('horizon', 'short')
    horizon_days = state.get('horizon_days', 10)
    
    # Fetch real-time price context
    try:
        simulated_date = state.get("simulated_date") or state.get("run_config", {}).get("simulated_date")
        risk_metrics = calculate_ticker_risk_metrics(ticker, as_of=simulated_date)
        current_price_str = risk_metrics.get("current_price", "Unknown") # e.g. "$135.50"
    except Exception:
        current_price_str = "Unknown"
    
    # Fallback to direct arguments if investment_plan not available
    if not investment_plan:
        arguments = state.get('arguments', {})
        bullish = arguments.get('bullish', '')
        bearish = arguments.get('bearish', '')
        context = f"Bullish Argument:\n{bullish}\n\nBearish Argument:\n{bearish}"
    else:
        context = f"Research Manager's Investment Plan:\n{investment_plan}"
    
    # 1. Construct the prompt for the LLM
    prompt = f"""Create an actionable trading strategy based on research analysis for {ticker}.

TRADING HORIZON: {horizon.upper()} ({horizon_days} trading days)

CONTEXT:
Current Market Price: {current_price_str}
Research Plan:
{context}

INSTRUCTIONS:
1. Decide on a strategy: BUY, SELL, or HOLD for the next {horizon_days} trading days.
2. IF BUY/SELL: Set 'entry_price' CLOSE to the Current Market Price ({current_price_str}).
   - For LONG (Buy): Take Profit > Entry > Stop Loss.
   - For SHORT (Sell): Stop Loss > Entry > Take Profit.
3. HOLD is allowed, but only if BOTH are true:
    - The evidence is genuinely mixed/insufficient to choose direction, AND
    - You can state at least two concrete blockers (e.g., conflicting signals, missing key info, imminent event risk).
    If there is a slight edge but uncertainty remains, prefer BUY/SELL with a SMALLER position_size_pct (e.g., 5–15) rather than HOLD.
4. Your recommendation is explicitly for a {horizon} horizon ({horizon_days} trading days).

Return ONLY valid JSON (no commentary or Markdown) in this exact schema:
{{
    "action": "BUY|SELL|HOLD",
    "entry_price": <number>,
    "take_profit": <number>,
    "stop_loss": <number>,
    "position_size_pct": <number>,
    "rationale": "<your reasoning in 1-2 sentences>"
}}

Keep response under 200 words."""
    
    # 2. Call the LLM to generate the strategy
    strategy_response = call_llm(prompt)
    
    # 3. Parse and validate JSON output
    try:
        json_text = _extract_json_from_text(strategy_response)
        strategy_model = TradingStrategy.model_validate_json(json_text)
        strategy = strategy_model.model_dump()
    except (ValueError, ValidationError) as exc:
        strategy = {
            "action": "HOLD",
            "entry_price": None,
            "take_profit": None,
            "stop_loss": None,
            "position_size_pct": 0,
            "rationale": f"Fallback due to parse/validation error: {exc}. Raw response: {strategy_response}",
        }

    # Normalize HOLD to avoid misleading price fields
    if (strategy.get("action") or "").upper() == "HOLD":
        strategy["entry_price"] = None
        strategy["take_profit"] = None
        strategy["stop_loss"] = None
        strategy["position_size_pct"] = 0
    
    # 4. Update the state
    state['trading_strategy'] = strategy
    
    return state


# ============================================================================
# REMOVED AGENTS - These were redundant and have been disabled
# See documentation/claude_context/WHY_TRADERS_REDUNDANT.md for explanation
# ============================================================================

# def arbitrage_trader_agent(state: dict):
#     """
#     REMOVED: Arbitrage Trader Agent
#     
#     Reason: Required complex real-time options data not available.
#     Used dummy data which made analysis meaningless.
#     Arbitrage trading is out of scope for stock analysis system.
#     """
#     pass

# def value_trader_agent(state: dict):
#     """
#     REMOVED: Value Trader Agent
#     
#     Reason: 95% overlap with Fundamental Analyst.
#     Both analyzed financial statements, valuation metrics, and competitive position.
#     Fundamental Analyst already provides comprehensive value assessment.
#     """
#     pass

# def bull_trader_agent(state: dict):
#     """
#     REMOVED: Bull Trader Agent
#     
#     Reason: 90% overlap with Bull Researcher.
#     Both made bullish case using growth catalysts, momentum, and sentiment.
#     Created confusion by arguing bull case twice in same analysis.
#     Bull Researcher in debate mechanism already provides this perspective.
#     """
#     pass