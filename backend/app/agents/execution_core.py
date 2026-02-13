# In nexustrader/backend/app/agents/execution_core.py

"""
Execution Core — Trader Agent

Architecture (Feb 12, 2026 — aligned with TradingAgents paper):

The Trader is an INDEPENDENT decision-maker, not a rubber-stamp.
It receives the Research Manager's investment plan as a *suggestion*
and makes its OWN BUY/SELL/HOLD call based on:
  1. The investment plan (context, not constraint)
  2. Current price + risk metrics
  3. Its own judgement

The Trader's action may DIFFER from the Research Manager's.
This creates the decision-tension that the Risk Debate needs to function.

Removed Agents (Redundant):
- Arbitrage Trader: Required complex options data not available
- Value Trader: Duplicated Fundamental Analyst's work (95% overlap)
- Bull Trader: Duplicated Bull Researcher's perspective (90% overlap)
"""

from ..llm import invoke_llm as call_llm, invoke_llm_quick
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
        # Use minimal thinking — this is a trivial extraction task
        signal = invoke_llm_quick(prompt).strip().upper()
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
    The Trader Agent (formerly "Strategy Synthesizer").
    
    Architecture (Feb 12, 2026 — aligned with TradingAgents paper):
    Receives the Research Manager's investment plan as CONTEXT (not constraint).
    Makes its OWN independent BUY/SELL/HOLD decision.
    This creates decision-tension for the downstream Risk Debate.
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
        current_price_str = risk_metrics.get("current_price", "Unknown")
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
    
    # NOTE: No extract_signal call here — we don't force alignment.
    # The Trader reads the plan and makes its own call.
    
    prompt = f"""You are the Trader for {ticker}. You have received an investment plan from the Research Manager.
Your job is to make your OWN independent trading decision. You may AGREE or DISAGREE with the plan.

TRADING HORIZON: {horizon.upper()} ({horizon_days} trading days)

CONTEXT:
Current Market Price: {current_price_str}
{context}

INSTRUCTIONS:
1. Evaluate the Research Manager's plan critically. Do you agree with the direction?
2. Make YOUR OWN decision: BUY, SELL, or HOLD for the next {horizon_days} trading days.
3. IF BUY/SELL: Set 'entry_price' CLOSE to the Current Market Price ({current_price_str}).
   - For LONG (Buy): Take Profit > Entry > Stop Loss.
   - For SHORT (Sell): Stop Loss > Entry > Take Profit.
4. HOLD is valid when evidence is genuinely mixed, but prefer a directional call
   with smaller position_size_pct (5-15%) over HOLD when there is any edge.
5. If you DISAGREE with the Research Manager, explain why in rationale.

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
    parse_failed = False
    try:
        json_text = _extract_json_from_text(strategy_response)
        strategy_model = TradingStrategy.model_validate_json(json_text)
        strategy = strategy_model.model_dump()
    except (ValueError, ValidationError) as exc:
        parse_failed = True
        # JSON parsing failed - use LLM signal extractor as fallback
        try:
            extracted_action = extract_signal(strategy_response, ticker)
            strategy = {
                "action": extracted_action,
                "entry_price": None,
                "take_profit": None,
                "stop_loss": None,
                "position_size_pct": 10 if extracted_action != "HOLD" else 0,
                "rationale": f"Extracted from prose after JSON parse failure: {exc}. Original response: {strategy_response[:200]}...",
            }
        except Exception as extract_exc:
            strategy = {
                "action": "HOLD",
                "entry_price": None,
                "take_profit": None,
                "stop_loss": None,
                "position_size_pct": 0,
                "rationale": f"Fallback due to parse error ({exc}) and extraction error ({extract_exc}). Raw: {strategy_response[:200]}...",
            }
    
    # NO forced alignment — Trader is independent.
    # Extract what the Research Manager recommended for metadata/risk debate context
    manager_action = None
    if investment_plan and len(investment_plan.strip()) > 50:
        # Simple keyword extraction (no LLM call needed)
        plan_upper = investment_plan.upper()
        if "RECOMMENDATION: BUY" in plan_upper or "RECOMMENDATION:** BUY" in plan_upper or "**BUY**" in plan_upper:
            manager_action = "BUY"
        elif "RECOMMENDATION: SELL" in plan_upper or "RECOMMENDATION:** SELL" in plan_upper or "**SELL**" in plan_upper:
            manager_action = "SELL"
        elif "RECOMMENDATION: HOLD" in plan_upper or "RECOMMENDATION:** HOLD" in plan_upper or "**HOLD**" in plan_upper:
            manager_action = "HOLD"
    
    trader_action = strategy.get("action", "HOLD")
    disagreed = manager_action and trader_action != manager_action
    if disagreed:
        print(f"[TRADER] Independent decision: Trader chose {trader_action}, Research Manager recommended {manager_action}")
    
    # Normalize HOLD to avoid misleading price fields
    if (strategy.get("action") or "").upper() == "HOLD":
        strategy["entry_price"] = None
        strategy["take_profit"] = None
        strategy["stop_loss"] = None
        strategy["position_size_pct"] = 0
    
    # 5. Update the state
    state['trading_strategy'] = strategy
    
    # Store both recommendations for Risk Manager to see the tension
    state['research_manager_recommendation'] = manager_action or "UNKNOWN"
    state['trader_recommendation'] = trader_action

    # Record run metadata for evaluation/debug
    if 'run_metadata' not in state:
        state['run_metadata'] = {}
    state['run_metadata'].update({
        "strategy_action": trader_action,
        "strategy_json_parse_failed": parse_failed,
        "research_manager_action": manager_action,
        "trader_disagreed_with_manager": disagreed,
    })
    
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