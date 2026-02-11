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


def extract_signal(text: str, ticker: str = "Unknown") -> str:
    """
    LLM-based signal extractor that replaces fragile keyword matching.
    
    When JSON parsing fails or output is ambiguous, this function uses an LLM
    to extract the trading signal (BUY/SELL/HOLD) from natural language text.
    
    This is more robust than regex patterns and can handle:
    - Conversational responses ("I recommend buying...")
    - Embedded signals in long explanations
    - Ambiguous phrasing ("accumulate positions" → BUY)
    - Multi-paragraph responses
    
    Args:
        text: The raw text response from an agent
        ticker: The ticker symbol (for context)
    
    Returns:
        One of: "BUY", "SELL", or "HOLD"
    """
    prompt = f"""Extract the trading signal from this analysis for {ticker}.

ANALYSIS TEXT:
{text}

INSTRUCTIONS:
- Return ONLY one word: BUY, SELL, or HOLD
- Look for explicit recommendations ("I recommend...", "Action: ...", "Decision: ...")
- Interpret synonyms:
  - BUY signals: "buy", "long", "accumulate", "add", "bullish", "go long"
  - SELL signals: "sell", "short", "exit", "reduce", "bearish", "go short"
  - HOLD signals: "hold", "wait", "neutral", "no action", "uncertain"
- If multiple signals exist, prioritize the FINAL recommendation
- If truly ambiguous, default to HOLD

Return ONLY: BUY, SELL, or HOLD (no punctuation, no explanation)"""
    
    try:
        signal = call_llm(prompt).strip().upper()
        # Validate the response
        if signal in ["BUY", "SELL", "HOLD"]:
            return signal
        # Fallback: check if response contains one of the keywords
        if "BUY" in signal:
            return "BUY"
        elif "SELL" in signal:
            return "SELL"
        else:
            return "HOLD"
    except Exception:
        # If LLM extraction itself fails, default to HOLD
        return "HOLD"


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
    # Extract the Research Manager's action directive using LLM signal extractor
    # Only used as a constraint to keep Strategy Synthesizer aligned with Research Manager
    # NOTE: Only call extract_signal if we have a substantive investment plan to extract from
    manager_action = None
    if investment_plan and len(investment_plan.strip()) > 50:
        try:
            manager_action = extract_signal(investment_plan, ticker)
        except Exception:
            manager_action = None
    
    action_constraint = ""
    if manager_action:
        action_constraint = f"\n\n⚠️ CRITICAL: The Research Manager has recommended {manager_action}. You MUST set 'action' to '{manager_action}' unless there are extreme execution impossibilities (e.g., no liquidity, circuit breaker). Your role is to translate the strategic decision into tactical parameters (entry, stop, take profit, position size), NOT to override the strategic decision.\n"
    
    prompt = f"""Create an actionable trading strategy based on research analysis for {ticker}.

TRADING HORIZON: {horizon.upper()} ({horizon_days} trading days)

CONTEXT:
Current Market Price: {current_price_str}
Research Plan:
{context}
{action_constraint}
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
        # JSON parsing failed - use LLM signal extractor as fallback
        # This prevents blind HOLD defaults when LLM gave valid recommendation in prose
        try:
            extracted_action = extract_signal(strategy_response, ticker)
            strategy = {
                "action": extracted_action,
                "entry_price": None,
                "take_profit": None,
                "stop_loss": None,
                "position_size_pct": 10 if extracted_action != "HOLD" else 0,  # Conservative 10% if BUY/SELL
                "rationale": f"Extracted from prose after JSON parse failure: {exc}. Original response: {strategy_response[:200]}...",
            }
        except Exception as extract_exc:
            # If signal extraction also fails, then default to HOLD
            strategy = {
                "action": "HOLD",
                "entry_price": None,
                "take_profit": None,
                "stop_loss": None,
                "position_size_pct": 0,
                "rationale": f"Fallback due to parse error ({exc}) and extraction error ({extract_exc}). Raw: {strategy_response[:200]}...",
            }
    
    # 4. ENFORCE consistency with Research Manager's decision
    # If Research Manager gave a clear directive, Strategy Synthesizer MUST respect it
    # Only Risk Manager can override this decision (not Strategy Synthesizer)
    if manager_action and manager_action != "HOLD":
        # Force alignment if LLM ignored the constraint
        if strategy.get("action") != manager_action:
            print(f"[CONSISTENCY] Strategy Synthesizer tried to override {manager_action} with {strategy.get('action')}. Enforcing Research Manager's decision.")
            strategy["action"] = manager_action
            # Adjust rationale to reflect enforcement
            original_rationale = strategy.get("rationale", "")
            strategy["rationale"] = f"[Enforced: Research Manager recommended {manager_action}] {original_rationale}"
    
    # Normalize HOLD to avoid misleading price fields
    if (strategy.get("action") or "").upper() == "HOLD":
        strategy["entry_price"] = None
        strategy["take_profit"] = None
        strategy["stop_loss"] = None
        strategy["position_size_pct"] = 0
    
    # 5. Update the state
    state['trading_strategy'] = strategy
    
    # Store Research Manager's original recommendation for Risk Manager to see
    if manager_action:
        state['research_manager_recommendation'] = manager_action
    
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