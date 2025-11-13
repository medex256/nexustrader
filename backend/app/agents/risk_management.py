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
    portfolio = get_portfolio_composition()
    volatility = get_market_volatility_index()
    var = calculate_portfolio_VaR(portfolio)
    correlation = get_correlation_matrix(portfolio)
    
    # 1. Construct the prompt for the LLM
    prompt = f"""Monitor and assess trading portfolio risk.

Data:
Portfolio Composition: {portfolio}
Market Volatility (VIX): {volatility}
Portfolio VaR: {var}
Asset Correlation Matrix: {correlation}

Provide:
- Overall exposure to risk factors
- Warnings if thresholds exceeded with corrective actions
- Concise risk assessment

Keep response under 250 words. Be conversational."""
    
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
