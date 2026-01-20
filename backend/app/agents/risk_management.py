# In nexustrader/backend/app/agents/risk_management.py

"""
Risk Management Agents

This module contains agents responsible for assessing portfolio risk
and validating trading strategies.

Active Agents:
- Risk Management Agent: Monitors portfolio risk and validates strategies

Removed Agents:
- Compliance Agent: Moved to Risk Manager's responsibilities for MVP
  (Can be re-added in future versions if needed)
"""

from ..tools.portfolio_tools import (
    get_market_volatility_index,
    get_portfolio_composition,
    calculate_portfolio_VaR,
    get_correlation_matrix,
    # New real tools
    calculate_ticker_risk_metrics,
    # Removed compliance-specific imports (now handled by Risk Manager if needed)
    # get_restricted_securities_list,
    # get_position_size_limits,
    # check_trade_compliance,
    # log_compliance_check,
)
from ..llm import invoke_llm as call_llm


def risk_management_agent(state: dict):
    """
    The Risk Management Agent.
    """
    ticker = state.get("ticker", "Unknown")
    
    # Use the real VIX
    volatility_index = get_market_volatility_index()
    
    # Calculate real risk metrics for the specific ticker
    ticker_risk = calculate_ticker_risk_metrics(ticker)
    
    # 1. Construct the prompt for the LLM
    prompt = f"""Monitor and assess risk for ticker: {ticker}

Data:
Market Volatility (VIX): {volatility_index}
Ticker Specific Risk Metrics: {ticker_risk}

Your Task:
1. Analyze the volatility and drawdown of {ticker}.
2. Compare it against the market VIX context.
3. Validate if the proposed trading strategy (if any) aligns with this risk profile.

Provide:
- Risk Rating (LOW/MED/HIGH)
- Max Recommended Position Size (conservative estimate based on volatility)
- Specific Stop-Loss recommendation based on 1Y Max Drawdown or Volatility.

Keep response under 200 words. Be strict."""
    
    # 2. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 3. Update the state
    if 'risk_reports' not in state:
        state['risk_reports'] = {}
    state['risk_reports']['portfolio_risk'] = analysis_report
    
    return state


# ============================================================================
# REMOVED AGENT - Compliance checking moved to Risk Manager for MVP
# ============================================================================

# def compliance_agent(state: dict):
#     """
#     REMOVED: Compliance Agent
#     
#     Reason: Overkill for MVP. Basic compliance checks can be handled
#     by Risk Management Agent. Can be re-added in v2.0 if specific
#     regulatory compliance features are needed.
#     """
#     pass
