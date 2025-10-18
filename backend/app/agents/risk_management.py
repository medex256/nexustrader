# In nexustrader/backend/app/agents/risk_management.py

from ..tools.portfolio_tools import (
    get_market_volatility_index,
    get_portfolio_composition,
    calculate_portfolio_VaR,
    get_correlation_matrix,
    get_restricted_securities_list,
    get_position_size_limits,
    check_trade_compliance,
    log_compliance_check,
)

# This is a placeholder for the actual LLM call
def call_llm(prompt: str):
    print("---")
    print("Calling LLM with prompt:")
    print(prompt)
    print("---")
    return "This is a dummy response from the LLM."

def risk_management_agent(state: dict):
    """
    The Risk Management Agent.
    """
    portfolio = get_portfolio_composition()
    volatility = get_market_volatility_index()
    var = calculate_portfolio_VaR(portfolio)
    correlation = get_correlation_matrix(portfolio)
    
    # 1. Construct the prompt for the LLM
    prompt = f"""
Your mission is to continuously monitor and assess the risk of the trading portfolio.
You have been provided with the following information:

Portfolio Composition:
{portfolio}

Market Volatility (VIX):
{volatility}

Portfolio Value at Risk (VaR):
{var}

Asset Correlation Matrix:
{correlation}

Please perform the following tasks:
1.  Assess the portfolio's overall exposure to different risk factors.
2.  If any risk parameters exceed their predefined thresholds, issue a warning and suggest corrective actions.
3.  Summarize your risk assessment in a concise report.
"""
    
    # 2. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 3. Update the state
    if 'risk_reports' not in state:
        state['risk_reports'] = {}
    state['risk_reports']['portfolio_risk'] = analysis_report
    
    return state

def compliance_agent(state: dict):
    """
    The Compliance Agent.
    """
    proposed_trade = state.get('proposed_trade')
    
    if not proposed_trade:
        return state
        
    # 1. Perform compliance checks using tools
    compliance_result = check_trade_compliance(proposed_trade)
    log_compliance_check(proposed_trade, compliance_result)
    
    # 2. Update the state
    state['compliance_check'] = compliance_result
    
    return state
