# In nexustrader/backend/app/agents/risk_management.py

"""
Risk Management Agents

This module contains agents responsible for assessing portfolio risk
and validating trading strategies through multi-perspective debate.

Active Agents:
- Aggressive Risk Analyst: Advocates for taking calculated risks
- Conservative Risk Analyst: Focuses on downside protection
- Neutral Risk Analyst: Balances risk and reward
- Risk Manager (Judge): Evaluates debate and makes final decision

Architecture inspired by TradingAgents paper - uses adversarial debate
to prevent excessive conservatism (HOLD bias).
"""

from ..tools.portfolio_tools import (
    get_market_volatility_index,
    get_portfolio_composition,
    calculate_portfolio_VaR,
    get_correlation_matrix,
    # New real tools
    calculate_ticker_risk_metrics,
)
from ..llm import invoke_llm as call_llm, invoke_llm_deep
from .execution_core import extract_signal


# ==============================================================================
# RISK DEBATE AGENTS (NEW: Feb 11, 2026)
# ==============================================================================

def aggressive_risk_analyst(state: dict):
    """
    The Aggressive Risk Analyst - Advocates for taking calculated risks.
    
    Role: Challenge conservative thinking and HOLD recommendations.
    Focus: Opportunity cost, growth potential, competitive positioning.
    """
    ticker = state.get("ticker", "Unknown")
    run_config = state.get("run_config", {})
    simulated_date = state.get("simulated_date") or run_config.get("simulated_date")
    
    # Initialize risk debate state if needed
    if 'risk_debate_state' not in state or state['risk_debate_state'] is None:
        state['risk_debate_state'] = {
            'history': '',
            'aggressive_history': '',
            'conservative_history': '',
            'neutral_history': '',
            'latest_speaker': '',
            'count': 0,
        }
    
    debate_state = state['risk_debate_state']
    strategy = state.get("trading_strategy", {}) or {}
    action = (strategy.get("action") or "HOLD").upper()
    
    # Surface RM vs Trader tension
    rm_action = state.get("research_manager_recommendation", "UNKNOWN")
    trader_action = state.get("trader_recommendation", action)
    disagreement_note = ""
    if rm_action != "UNKNOWN" and rm_action != trader_action:
        disagreement_note = f"\n\n⚠️ IMPORTANT DISAGREEMENT: Research Manager recommended {rm_action}, but the Trader independently decided {trader_action}. This disagreement is a key signal — address which side has better reasoning.\n"
    
    # Get market context
    volatility_index = get_market_volatility_index()
    ticker_risk = calculate_ticker_risk_metrics(ticker, as_of=simulated_date)
    
    # Get other analysts' arguments to respond to
    conservative_last = debate_state.get('conservative_history', '')
    neutral_last = debate_state.get('neutral_history', '')
    
    # Build prompt
    if debate_state['count'] == 0:
        # First round - opening argument
        prompt = f"""You are the Aggressive Risk Analyst for {ticker}. Your role is to advocate for BOLD ACTION and challenge excessive caution.

The Trader recommends: {action}
Research Manager recommended: {rm_action}
{disagreement_note}
Market Context:
- VIX: {volatility_index}
- Ticker Risk: {ticker_risk}

Strategy Details:
{strategy}

Your Task:
{"The recommendation is HOLD. Evaluate whether there is an opportunity being missed. What is the cost of inaction vs the risk of acting?" if action == "HOLD" else f"The recommendation is {action}. Argue whether the conviction is strong enough and whether position sizing should be more aggressive."}

Focus on:
- Opportunity cost of sitting on sidelines
- Growth potential and competitive advantages
- Why this is the RIGHT time to act
- What we LOSE by being too cautious

Be direct and persuasive. Challenge conservative thinking. Start with "Aggressive Analyst:"."""
    else:
        # Subsequent rounds - respond to other analysts
        prompt = f"""You are the Aggressive Risk Analyst in a debate about {ticker}.

Strategy: {action}
Market Context: VIX {volatility_index}, Risk {ticker_risk}

Conservative Analyst argued:
{conservative_last[-800:] if conservative_last else "N/A"}

Neutral Analyst argued:
{neutral_last[-800:] if neutral_last else "N/A"}

Your Previous Points:
{debate_state.get('aggressive_history', '')[-500:]}

Counter their caution with specific rebuttals:
- Where are they being overly risk-averse?
- What opportunities are they overlooking?
- Why is their fear preventing profit?

Be confrontational and data-driven. Start with "Aggressive Analyst:"."""
    
    # Generate response
    response = call_llm(prompt)
    
    # Update debate state
    debate_state['aggressive_history'] += f"\n\n{response}"
    debate_state['history'] += f"\n\n{response}"
    debate_state['latest_speaker'] = "Aggressive"
    debate_state['count'] += 1
    
    state['risk_debate_state'] = debate_state
    return state


def conservative_risk_analyst(state: dict):
    """
    The Conservative Risk Analyst - Focuses on downside protection.
    
    Role: Identify risks and potential losses.
    Focus: Volatility, drawdowns, worst-case scenarios.
    """
    ticker = state.get("ticker", "Unknown")
    run_config = state.get("run_config", {})
    simulated_date = state.get("simulated_date") or run_config.get("simulated_date")
    
    debate_state = state.get('risk_debate_state', {})
    strategy = state.get("trading_strategy", {}) or {}
    action = (strategy.get("action") or "HOLD").upper()
    
    # Surface RM vs Trader tension
    rm_action = state.get("research_manager_recommendation", "UNKNOWN")
    trader_action = state.get("trader_recommendation", action)
    disagreement_note = ""
    if rm_action != "UNKNOWN" and rm_action != trader_action:
        disagreement_note = f"\n\n⚠️ IMPORTANT DISAGREEMENT: Research Manager recommended {rm_action}, but the Trader independently decided {trader_action}. This disagreement is a key signal — address whether the Trader is taking on too much risk.\n"
    
    # Get market context
    volatility_index = get_market_volatility_index()
    ticker_risk = calculate_ticker_risk_metrics(ticker, as_of=simulated_date)
    
    # Get other analysts' arguments
    aggressive_last = debate_state.get('aggressive_history', '')
    neutral_last = debate_state.get('neutral_history', '')
    
    # Build prompt
    if debate_state['count'] == 1:
        # First response (after aggressive opened)
        prompt = f"""You are the Conservative Risk Analyst for {ticker}. Your role is to protect capital and minimize losses.

The Trader recommends: {action}
Research Manager recommended: {rm_action}
{disagreement_note}

Market Context:
- VIX: {volatility_index}
- Ticker Risk: {ticker_risk}

Strategy Details:
{strategy}

Aggressive Analyst argued:
{aggressive_last[-800:] if aggressive_last else "N/A"}

Your Task:
{"Defend the HOLD recommendation - explain why action is RISKY right now." if action == "HOLD" else f"Challenge the {action} recommendation - what could go WRONG?"}

Focus on:
- Downside risks and potential losses
- Market volatility and uncertainty
- Historical drawdowns and red flags
- Why caution is prudent given current conditions

Be rigorous and risk-aware. Start with "Conservative Analyst:"."""
    else:
        # Subsequent rounds
        prompt = f"""You are the Conservative Risk Analyst in a debate about {ticker}.

Strategy: {action}
Market Context: VIX {volatility_index}, Risk {ticker_risk}

Aggressive Analyst argued:
{aggressive_last[-800:] if aggressive_last else "N/A"}

Neutral Analyst argued:
{neutral_last[-800:] if neutral_last else "N/A"}

Your Previous Points:
{debate_state.get('conservative_history', '')[-500:]}

Rebut their optimism with specific risks:
- Where are they underestimating downside?
- What volatility/drawdown risks are they ignoring?
- Why could this trade result in significant loss?

Be skeptical and protective. Start with "Conservative Analyst:"."""
    
    # Generate response
    response = call_llm(prompt)
    
    # Update debate state
    debate_state['conservative_history'] += f"\n\n{response}"
    debate_state['history'] += f"\n\n{response}"
    debate_state['latest_speaker'] = "Conservative"
    debate_state['count'] += 1
    
    state['risk_debate_state'] = debate_state
    return state


def neutral_risk_analyst(state: dict):
    """
    The Neutral Risk Analyst - Balances risk and reward.
    
    Role: Find middle ground and optimal risk-adjusted approach.
    Focus: Risk-reward ratio, balanced position sizing, hedging.
    """
    ticker = state.get("ticker", "Unknown")
    run_config = state.get("run_config", {})
    simulated_date = state.get("simulated_date") or run_config.get("simulated_date")
    
    debate_state = state.get('risk_debate_state', {})
    strategy = state.get("trading_strategy", {}) or {}
    action = (strategy.get("action") or "HOLD").upper()
    
    # Surface RM vs Trader tension
    rm_action = state.get("research_manager_recommendation", "UNKNOWN")
    trader_action = state.get("trader_recommendation", action)
    disagreement_note = ""
    if rm_action != "UNKNOWN" and rm_action != trader_action:
        disagreement_note = f"\n\n⚠️ IMPORTANT DISAGREEMENT: Research Manager recommended {rm_action}, but the Trader independently decided {trader_action}. Evaluate which side has stronger evidence.\n"
    
    # Get market context
    volatility_index = get_market_volatility_index()
    ticker_risk = calculate_ticker_risk_metrics(ticker, as_of=simulated_date)
    
    # Get other analysts' arguments
    aggressive_last = debate_state.get('aggressive_history', '')
    conservative_last = debate_state.get('conservative_history', '')
    
    # Build prompt
    prompt = f"""You are the Neutral Risk Analyst for {ticker}. Your role is to find the optimal balanced approach.

The Trader recommends: {action}
Research Manager recommended: {rm_action}
{disagreement_note}

Market Context:
- VIX: {volatility_index}
- Ticker Risk: {ticker_risk}

Strategy Details:
{strategy}

Aggressive Analyst argued:
{aggressive_last[-800:] if aggressive_last else "N/A"}

Conservative Analyst argued:
{conservative_last[-800:] if conservative_last else "N/A"}

Your Previous Points:
{debate_state.get('neutral_history', '')[-500:] if debate_state.get('neutral_history') else "N/A"}

Your Task:
Evaluate both sides and propose a BALANCED solution.

Focus on:
- Where is the aggressive analyst right (and wrong)?
- Where is the conservative analyst right (and wrong)?
- What's the optimal risk-adjusted position?
- Should we modify position size, stops, or approach?

Be analytical and fair. Start with "Neutral Analyst:"."""
    
    # Generate response
    response = call_llm(prompt)
    
    # Update debate state
    debate_state['neutral_history'] += f"\n\n{response}"
    debate_state['history'] += f"\n\n{response}"
    debate_state['latest_speaker'] = "Neutral"
    debate_state['count'] += 1
    
    state['risk_debate_state'] = debate_state
    return state


# ==============================================================================
# RISK MANAGER (JUDGE) - Evaluates debate and makes final decision
# ==============================================================================

def risk_management_agent(state: dict):
    """
    The Risk Manager (Judge) - Evaluates risk debate and makes final decision.
    
    NEW: Acts as judge after 3-way risk debate (aggressive/conservative/neutral).
    FALLBACK: If risk debate disabled, acts as simple validator (legacy mode).
    """
    ticker = state.get("ticker", "Unknown")
    run_config = state.get("run_config", {})
    simulated_date = state.get("simulated_date") or run_config.get("simulated_date")
    
    # Get market context
    volatility_index = get_market_volatility_index()
    ticker_risk = calculate_ticker_risk_metrics(ticker, as_of=simulated_date)
    
    if 'risk_reports' not in state:
        state['risk_reports'] = {}
    
    # Check if risk debate occurred
    debate_state = state.get('risk_debate_state', {})
    debate_history = debate_state.get('history', '')
    
    # MODE 1: Judge Risk Debate (NEW)
    if debate_history:
        strategy = state.get("trading_strategy", {}) or {}
        original_action = (strategy.get("action") or "HOLD").upper()
        research_manager_action = state.get("research_manager_recommendation", "UNKNOWN")
        trader_action = state.get("trader_recommendation", original_action)
        
        # Build disagreement context for the judge
        disagreement_context = ""
        if research_manager_action != "UNKNOWN" and research_manager_action != trader_action:
            disagreement_context = f"""\n⚠️ CRITICAL DISAGREEMENT: Research Manager recommended {research_manager_action}, but the Trader independently chose {trader_action}.
This disagreement is a KEY SIGNAL. Evaluate which side has stronger reasoning.
The risk debate above was informed by this disagreement.\n"""
        else:
            disagreement_context = f"\n✅ Research Manager and Trader AGREE on {trader_action}.\n"
        
        prompt = f"""As the Risk Manager, evaluate this risk debate and make a FINAL DECISION for {ticker}.

Research Manager's Recommendation: {research_manager_action}
Trader's Independent Decision: {trader_action}
{disagreement_context}
Strategy Details: {strategy}

Market Context:
- VIX: {volatility_index}
- Ticker Risk: {ticker_risk}

Complete Risk Debate:
{debate_history}

Your Task:
1. **Summarize** key points from each analyst (aggressive/conservative/neutral)
2. **Evaluate the RM vs Trader disagreement** (if any) — who has better reasoning?
3. **Make Final Decision**: BUY, SELL, or HOLD
   - You CAN override both the Research Manager AND the Trader if the debate surfaces critical flaws
   - HOLD is valid when conviction is genuinely low or risk/reward is unclear
   - BUY and SELL require clear directional conviction supported by at least 2 analysts
4. **Adjust Strategy** (if changing from Trader's decision):
   - Position size (% of portfolio)
   - Stop loss / Take profit levels

Decision Rules:
- If RM and Trader agree + 2 of 3 analysts agree → high conviction, go with it
- If RM and Trader disagree → weigh the debate carefully, side with stronger evidence
- If all 3 analysts raise significant concerns → override to HOLD
- If evidence is genuinely mixed → HOLD is appropriate

Format:
## Risk Manager Final Decision

**Research Manager Recommended**: {research_manager_action}
**Trader Decided**: {trader_action}
**Final Decision**: [BUY/SELL/HOLD]

**Rationale**: [2-3 sentences explaining your decision]

**Adjustments**:
- Position Size: [X%]
- Stop Loss: [price]
- Take Profit: [price]

Keep response under 300 words."""
        
        # Generate final decision using DEEP thinking (judge role)
        final_decision = invoke_llm_deep(prompt)
        
        # Extract decision using LLM signal extractor (robust, replaces keyword matching)
        try:
            final_action = extract_signal(final_decision, ticker)
        except Exception:
            # Fallback: keep original action
            final_action = original_action
        
        # Update strategy with final decision
        strategy["action"] = final_action
        
        # Apply risk gates based on final decision
        if final_action != "HOLD":
            risk_rating = (ticker_risk.get("risk_rating") or "MODERATE").upper()
            max_position_pct = 8 if risk_rating == "HIGH" else 15 if risk_rating == "MODERATE" else 25
            
            old_position = strategy.get("position_size_pct", 0) or 0
            new_position = min(float(old_position), float(max_position_pct)) if old_position else float(max_position_pct)
            strategy["position_size_pct"] = round(new_position, 2)
            
            # Ensure sensible stop/take profit
            entry_price = strategy.get("entry_price")
            if entry_price:
                if final_action == "BUY":
                    if not strategy.get("stop_loss") or strategy.get("stop_loss", 0) >= entry_price:
                        strategy["stop_loss"] = round(entry_price * 0.92, 2)
                    if not strategy.get("take_profit") or strategy.get("take_profit", 0) <= entry_price:
                        strategy["take_profit"] = round(entry_price * 1.12, 2)
                elif final_action == "SELL":
                    if not strategy.get("stop_loss") or strategy.get("stop_loss", 0) <= entry_price:
                        strategy["stop_loss"] = round(entry_price * 1.08, 2)
                    if not strategy.get("take_profit") or strategy.get("take_profit", 0) >= entry_price:
                        strategy["take_profit"] = round(entry_price * 0.88, 2)
        else:
            # HOLD - clear out price fields
            strategy["entry_price"] = None
            strategy["take_profit"] = None
            strategy["stop_loss"] = None
            strategy["position_size_pct"] = 0
        
        state['trading_strategy'] = strategy
        state['proposed_trade'] = strategy
        state['risk_reports']['risk_manager_decision'] = final_decision
        state['risk_reports']['risk_gate'] = f"Risk debate evaluated. Original: {original_action}, Final: {final_action}"

        # Record run metadata for evaluation/debug
        if 'run_metadata' not in state:
            state['run_metadata'] = {}
        state['run_metadata'].update({
            "risk_original_action": original_action,
            "risk_final_action": final_action,
            "risk_overrode_action": original_action != final_action,
        })
        
        return state
    
    # MODE 2: Legacy Validator (risk debate disabled)
    # This is the old behavior - simple risk gate without debate
    if not run_config.get("risk_on", True):
        state['risk_reports']['risk_gate'] = "Risk gating disabled by run_config (risk_on=false). No adjustments applied."
        if 'run_metadata' not in state:
            state['run_metadata'] = {}
        state['run_metadata'].update({
            "risk_original_action": (state.get("trading_strategy", {}) or {}).get("action"),
            "risk_final_action": (state.get("trading_strategy", {}) or {}).get("action"),
            "risk_overrode_action": False,
        })
        return state
    
    strategy = state.get("trading_strategy", {}) or {}
    action = (strategy.get("action") or "HOLD").upper()
    
    if action == "HOLD":
        state['risk_reports']['risk_gate'] = "No trade action (HOLD). Risk gate made no changes."
        if 'run_metadata' not in state:
            state['run_metadata'] = {}
        state['run_metadata'].update({
            "risk_original_action": action,
            "risk_final_action": action,
            "risk_overrode_action": False,
        })
        return state
    
    # Simple risk gate adjustments (legacy path)
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
        f"Legacy risk gate applied (debate disabled). risk_rating={risk_rating}, max_position_pct={max_position_pct}. "
        f"position_size_pct {old_position} -> {strategy.get('position_size_pct')}."
    )

    if 'run_metadata' not in state:
        state['run_metadata'] = {}
    state['run_metadata'].update({
        "risk_original_action": action,
        "risk_final_action": strategy.get("action"),
        "risk_overrode_action": action != strategy.get("action"),
    })
    
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
