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
# Removed unused imports for redundant traders
# from ..tools.derivatives_tools import get_option_chain, calculate_put_call_parity
# from ..tools.financial_data_tools import get_financial_statements, get_key_valuation_metrics, get_competitor_list, get_analyst_ratings
# from ..tools.social_media_tools import search_twitter, search_reddit
# from ..tools.news_tools import search_news
# from ..tools.market_data_tools import get_market_sentiment
# from ..utils.shared_context import shared_context


def trading_strategy_synthesizer_agent(state: dict):
    """
    The Trading Strategy Synthesizer Agent.
    Now uses the investment_plan from the Research Manager.
    """
    # Get the investment plan from research manager
    investment_plan = state.get('investment_plan', '')
    
    # Fallback to direct arguments if investment_plan not available
    if not investment_plan:
        arguments = state.get('arguments', {})
        bullish = arguments.get('bullish', '')
        bearish = arguments.get('bearish', '')
        context = f"Bullish Argument:\n{bullish}\n\nBearish Argument:\n{bearish}"
    else:
        context = f"Research Manager's Investment Plan:\n{investment_plan}"
    
    # 1. Construct the prompt for the LLM
    prompt = f"""Create an actionable trading strategy based on research analysis.

{context}

Provide a decisive strategy: BUY, SELL, or HOLD.
For BUY/SELL, specify: entry price, take-profit, stop-loss, position size (% of portfolio).

Format as JSON:
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
    
    # 3. Parse the LLM response to get the structured strategy
    # TODO: Implement proper JSON parsing with error handling
    # For now, use a placeholder structure
    import re
    import json
    
    try:
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', strategy_response, re.DOTALL)
        if json_match:
            strategy = json.loads(json_match.group())
        else:
            # Fallback to placeholder
            strategy = {
                "action": "HOLD",
                "entry_price": None,
                "take_profit": None,
                "stop_loss": None,
                "position_size_pct": 0,
                "rationale": strategy_response,
            }
    except:
        # If parsing fails, use placeholder
        strategy = {
            "action": "HOLD",
            "entry_price": None,
            "take_profit": None,
            "stop_loss": None,
            "position_size_pct": 0,
            "rationale": strategy_response,
        }
    
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