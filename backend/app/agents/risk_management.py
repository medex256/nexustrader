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
    run_config = state.get("run_config", {})
    simulated_date = state.get("simulated_date") or run_config.get("simulated_date")
    
    # Use the real VIX
    volatility_index = get_market_volatility_index()
    
    # Calculate real risk metrics for the specific ticker
    ticker_risk = calculate_ticker_risk_metrics(ticker, as_of=simulated_date)
    
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

    # If risk gating is disabled, skip adjustments
    if not run_config.get("risk_on", True):
        state['risk_reports']['risk_gate'] = "Risk gating disabled by run_config (risk_on=false). No adjustments applied."
        return state

    # Apply simple risk gate adjustments to the proposed strategy
    strategy = state.get("trading_strategy", {}) or {}
    action = (strategy.get("action") or "HOLD").upper()

    if action == "HOLD":
        state['risk_reports']['risk_gate'] = "No trade action (HOLD). Risk gate made no changes."
        return state

    risk_rating = (ticker_risk.get("risk_rating") or "MODERATE").upper()
    max_position_pct = 8 if risk_rating == "HIGH" else 15 if risk_rating == "MODERATE" else 25

    old_position = strategy.get("position_size_pct", 0) or 0
    new_position = min(float(old_position), float(max_position_pct)) if old_position else float(max_position_pct)
    strategy["position_size_pct"] = round(new_position, 2)

    # Ensure stop-loss / take-profit exist and are sensible
    entry_price = strategy.get("entry_price")
    take_profit = strategy.get("take_profit")
    stop_loss = strategy.get("stop_loss")

    if entry_price:
        if action == "BUY":
            if not stop_loss or stop_loss >= entry_price:
                stop_loss = round(entry_price * 0.92, 2)
            if not take_profit or take_profit <= entry_price:
                take_profit = round(entry_price * 1.12, 2)
        elif action == "SELL":
            if not stop_loss or stop_loss <= entry_price:
                stop_loss = round(entry_price * 1.08, 2)
            if not take_profit or take_profit >= entry_price:
                take_profit = round(entry_price * 0.88, 2)

        strategy["stop_loss"] = stop_loss
        strategy["take_profit"] = take_profit

    state['trading_strategy'] = strategy
    state['proposed_trade'] = strategy
    state['risk_reports']['risk_gate'] = (
        f"Risk gate applied. risk_rating={risk_rating}, max_position_pct={max_position_pct}. "
        f"position_size_pct {old_position} -> {strategy.get('position_size_pct')}."
    )
    
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
