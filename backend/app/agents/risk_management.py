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

import re
from typing import Literal, Optional
from pydantic import BaseModel, Field

from ..tools.portfolio_tools import (
    get_market_volatility_index,
    get_portfolio_composition,
    calculate_portfolio_VaR,
    get_correlation_matrix,
    # New real tools
    calculate_ticker_risk_metrics,
)
from ..llm import invoke_llm as call_llm
from ..llm import invoke_llm_structured as call_llm_structured
from .execution_core import extract_signal


# ==============================================================================
# RISK DEBATE AGENTS (NEW: Feb 11, 2026)
# ==============================================================================

def _format_reports_for_risk_debate(state: dict) -> str:
    """
    Provide risk debaters with the same analyst evidence context used upstream.
    This aligns risk debate behavior with the reference architecture.
    """
    signals = state.get("signals", {}) or {}
    reports = state.get("reports", {}) or {}

    lines = ["**ANALYST SIGNAL SUMMARY**"]
    for key, label in [
        ("fundamental", "Fundamental"),
        ("technical", "Technical"),
        ("news", "News/Sentiment"),
    ]:
        if key in signals:
            s = signals[key]
            lines.append(
                f"- **{label}**: {s.get('direction', 'N/A')} "
                f"({s.get('confidence', 0.5):.0%} confidence) — {s.get('key_factor', '')}"
            )
        else:
            lines.append(f"- **{label}**: No signal available")

    lines.append("\n**DETAILED ANALYST REPORTS**")
    for key, label in [
        ("fundamental_analyst", "Fundamental Analysis"),
        ("technical_analyst", "Technical Analysis"),
        ("news_harvester", "News Analysis"),
    ]:
        if key in reports and reports.get(key):
            lines.append(f"\n### {label}\n{reports[key]}")

    return "\n".join(lines)

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
    
    # Get market context (as_of scopes VIX to historical date — fixes data leakage)
    volatility_index = get_market_volatility_index(as_of=simulated_date)
    ticker_risk = calculate_ticker_risk_metrics(ticker, as_of=simulated_date)
    
    # Get other analysts' arguments to respond to
    conservative_last = debate_state.get('conservative_history', '')
    neutral_last = debate_state.get('neutral_history', '')
    
    # Build prompt
    if debate_state['count'] == 0:
        # First round - opening argument
        prompt = f"""Role: Risk Analyst A for {ticker}.
    Task: identify why the current action may be too conservative.

    Trader action: {action}
    Research Manager action: {rm_action}
    {disagreement_note}
    Market Context: VIX={volatility_index}, TickerRisk={ticker_risk}
    Analyst Evidence:
    {_format_reports_for_risk_debate(state)}
    Strategy:
    {strategy}

    Use only provided context. No outside facts.

    Output:
    - KEY_POINT: 1 line
    - SUPPORTING_EVIDENCE: 2 bullets
    - RISK_IF_NO_ACTION: 1 bullet

    Keep under 160 words. Start with "Aggressive Analyst:"."""
    else:
        # Subsequent rounds - respond to other analysts
        prompt = f"""Role: Risk Analyst A in debate for {ticker}.
    Task: rebut the strongest conservative objections with evidence.

    Strategy: {action}
    Market: VIX={volatility_index}, Risk={ticker_risk}
    Evidence:
    {_format_reports_for_risk_debate(state)}
    Conservative view:
    {conservative_last if conservative_last else "N/A"}
    Neutral view:
    {neutral_last if neutral_last else "N/A"}

    Use only provided context.

    Output:
    - REBUTTALS: 2 bullets
    - UPDATED_VIEW: one line

    Keep under 140 words. Start with "Aggressive Analyst:"."""
    
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
    
    # Get market context (as_of scopes VIX to historical date — fixes data leakage)
    volatility_index = get_market_volatility_index(as_of=simulated_date)
    ticker_risk = calculate_ticker_risk_metrics(ticker, as_of=simulated_date)
    
    # Get other analysts' arguments
    aggressive_last = debate_state.get('aggressive_history', '')
    neutral_last = debate_state.get('neutral_history', '')
    
    # Build prompt
    if debate_state['count'] == 1:
        # First response (after aggressive opened)
        prompt = f"""Role: Risk Analyst B for {ticker}.
    Task: identify downside risks in the current action.

    Trader action: {action}
    Research Manager action: {rm_action}
    {disagreement_note}
    Market Context: VIX={volatility_index}, TickerRisk={ticker_risk}
    Analyst Evidence:
    {_format_reports_for_risk_debate(state)}
    Strategy:
    {strategy}
    Aggressive view:
    {aggressive_last if aggressive_last else "N/A"}

    Use only provided context. No outside facts.

    Output:
    - KEY_RISK: 1 line
    - SUPPORTING_EVIDENCE: 2 bullets
    - RISK_MITIGATION: 1 bullet

    Keep under 160 words. Start with "Conservative Analyst:"."""
    else:
        # Subsequent rounds
        prompt = f"""Role: Risk Analyst B in debate for {ticker}.
    Task: rebut the strongest optimistic claims with evidence.

    Strategy: {action}
    Market: VIX={volatility_index}, Risk={ticker_risk}
    Evidence:
    {_format_reports_for_risk_debate(state)}
    Aggressive view:
    {aggressive_last if aggressive_last else "N/A"}
    Neutral view:
    {neutral_last if neutral_last else "N/A"}

    Use only provided context.

    Output:
    - REBUTTALS: 2 bullets
    - UPDATED_VIEW: one line

    Keep under 140 words. Start with "Conservative Analyst:"."""
    
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
    
    # Get market context (as_of scopes VIX to historical date — fixes data leakage)
    volatility_index = get_market_volatility_index(as_of=simulated_date)
    ticker_risk = calculate_ticker_risk_metrics(ticker, as_of=simulated_date)
    
    # Get other analysts' arguments
    aggressive_last = debate_state.get('aggressive_history', '')
    conservative_last = debate_state.get('conservative_history', '')
    
    # Build prompt
    prompt = f"""Role: Risk Analyst Neutral for {ticker}.
Task: synthesize both sides and propose the most balanced risk-adjusted view.

Trader action: {action}
Research Manager action: {rm_action}
{disagreement_note}
Market Context: VIX={volatility_index}, TickerRisk={ticker_risk}
Evidence:
{_format_reports_for_risk_debate(state)}
Strategy:
{strategy}
Analyst A:
{aggressive_last if aggressive_last else "N/A"}
Analyst B:
{conservative_last if conservative_last else "N/A"}

Use only provided context.

Output:
- STRONGEST_PRO: 1 bullet
- STRONGEST_CON: 1 bullet
- BALANCED_RECOMMENDATION: BUY|SELL|HOLD (one line)
- POSITION_SIZE_GUIDANCE: one line

Keep under 170 words. Start with "Neutral Analyst:"."""
    
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

class RiskManagerDecision(BaseModel):
    final_decision: Literal["BUY", "SELL", "HOLD"]
    thesis_invalidated: Literal["YES", "NO"]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    rationale: str
    position_size_pct: float = Field(ge=0, le=100)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

def risk_management_agent(state: dict):
    """
    The Risk Manager (single risk-check judge) - evaluates strategy and finalizes action.
    """
    ticker = state.get("ticker", "Unknown")
    run_config = state.get("run_config", {})
    simulated_date = state.get("simulated_date") or run_config.get("simulated_date")
    
    # Get market context (as_of scopes VIX to historical date — fixes data leakage)
    volatility_index = get_market_volatility_index(as_of=simulated_date)
    ticker_risk = calculate_ticker_risk_metrics(ticker, as_of=simulated_date)
    
    if 'risk_reports' not in state:
        state['risk_reports'] = {}

    if (run_config.get("risk_mode", "single") or "single").lower() == "off":
        state['risk_reports']['risk_gate'] = "Risk gating disabled by run_config (risk_mode=off). No adjustments applied."
        if 'run_metadata' not in state:
            state['run_metadata'] = {}
        current_action = (state.get("trading_strategy", {}) or {}).get("action")
        state['run_metadata'].update({
            "risk_original_action": current_action,
            "risk_final_action": current_action,
            "risk_overrode_action": False,
        })
        return state
    
    strategy = state.get("trading_strategy", {}) or {}
    original_action = (strategy.get("action") or "HOLD").upper()
    research_manager_action = state.get("research_manager_recommendation", "UNKNOWN")
    trader_action = state.get("trader_recommendation", original_action)
    horizon = state.get('horizon') or run_config.get('horizon', 'short')
    horizon_days = state.get('horizon_days') or run_config.get('horizon_days', 10)

    disagreement_context = ""
    if research_manager_action != "UNKNOWN" and research_manager_action != trader_action:
        disagreement_context = f"""\n⚠️ DISAGREEMENT: Research Manager recommended {research_manager_action}, Trader chose {trader_action}.
Decide which side has stronger evidence for the next {horizon_days} trading days.\n"""
    else:
        disagreement_context = f"\n✅ No major disagreement: current directional action is {trader_action}.\n"

    prompt = f"""Role: Risk Manager.
Task: run a single risk-check and choose final BUY/SELL/HOLD for {ticker} over the next {horizon_days} trading days ({horizon}).

Research Manager Recommendation: {research_manager_action}
Trader Decision: {trader_action}
{disagreement_context}
Strategy Details: {strategy}

Analyst Evidence:
{_format_reports_for_risk_debate(state)}

Market Context:
- VIX: {volatility_index}
- Ticker Risk: {ticker_risk}

Use only provided evidence. No outside facts.
Apply symmetric criteria for BUY and SELL.

Decision policy:
1) Start from Trader direction ({trader_action}).
2) Change to HOLD only if thesis is explicitly invalidated by concrete contradictory evidence.
3) If evidence is mixed but not invalidating, keep direction and reduce size.

Confidence rubric:
- HIGH: 3+ aligned independent signals and no major contradiction.
- MEDIUM: 1-2 aligned signals with manageable contradiction.
- LOW: conflicting or weak evidence.

Output format:
FINAL DECISION: BUY|SELL|HOLD
THESIS_INVALIDATED: YES|NO
CONFIDENCE: HIGH|MEDIUM|LOW
RATIONALE:
- 2-4 sentences with strongest evidence and why opposite action was not chosen
ADJUSTMENTS:
- Position Size: [X%]
- Stop Loss: [price|null]
- Take Profit: [price|null]

Keep under 260 words."""

    structured_prompt = prompt + """

Return strict JSON with keys:
final_decision, thesis_invalidated, confidence, rationale, position_size_pct, stop_loss, take_profit
"""

    try:
        decision = call_llm_structured(
            structured_prompt,
            RiskManagerDecision,
            temperature=0.2,
        )
    except Exception as e:
        fallback_text = call_llm(prompt)
        fallback_action = extract_signal(fallback_text, ticker)
        decision = RiskManagerDecision(
            final_decision=fallback_action,
            thesis_invalidated="NO",
            confidence="LOW",
            rationale=f"Structured output failure: {e}. Fallback used.",
            position_size_pct=0 if fallback_action == "HOLD" else 10,
            stop_loss=None,
            take_profit=None,
        )

    final_decision = decision.model_dump_json(indent=2)
    final_action = decision.final_decision
    thesis_invalidated = decision.thesis_invalidated == "YES"
    if final_action == "HOLD" and trader_action in {"BUY", "SELL"} and not thesis_invalidated:
        final_action = trader_action

    strategy["action"] = final_action
    strategy["rationale"] = decision.rationale

    if final_action != "HOLD":
        risk_rating = (ticker_risk.get("risk_rating") or "MODERATE").upper()
        max_position_pct = 8 if risk_rating == "HIGH" else 15 if risk_rating == "MODERATE" else 25

        old_position = strategy.get("position_size_pct", 0) or 0
        model_position = float(decision.position_size_pct or 0)
        requested_position = model_position if model_position > 0 else float(old_position)
        new_position = min(float(requested_position), float(max_position_pct)) if requested_position else float(max_position_pct)
        strategy["position_size_pct"] = round(new_position, 2)

        entry_price = strategy.get("entry_price")
        if entry_price:
            if final_action == "BUY":
                if decision.stop_loss is not None:
                    strategy["stop_loss"] = decision.stop_loss
                elif not strategy.get("stop_loss") or strategy.get("stop_loss", 0) >= entry_price:
                    strategy["stop_loss"] = round(entry_price * 0.92, 2)
                if decision.take_profit is not None:
                    strategy["take_profit"] = decision.take_profit
                elif not strategy.get("take_profit") or strategy.get("take_profit", 0) <= entry_price:
                    strategy["take_profit"] = round(entry_price * 1.12, 2)
            elif final_action == "SELL":
                if decision.stop_loss is not None:
                    strategy["stop_loss"] = decision.stop_loss
                elif not strategy.get("stop_loss") or strategy.get("stop_loss", 0) <= entry_price:
                    strategy["stop_loss"] = round(entry_price * 1.08, 2)
                if decision.take_profit is not None:
                    strategy["take_profit"] = decision.take_profit
                elif not strategy.get("take_profit") or strategy.get("take_profit", 0) >= entry_price:
                    strategy["take_profit"] = round(entry_price * 0.88, 2)
    else:
        strategy["entry_price"] = None
        strategy["take_profit"] = None
        strategy["stop_loss"] = None
        strategy["position_size_pct"] = 0

    state['trading_strategy'] = strategy
    state['proposed_trade'] = strategy
    state['risk_reports']['risk_manager_decision'] = final_decision
    state['risk_reports']['risk_gate'] = f"Single risk-check evaluated. Original: {original_action}, Final: {final_action}"

    if 'run_metadata' not in state:
        state['run_metadata'] = {}
    state['run_metadata'].update({
        "risk_original_action": original_action,
        "risk_final_action": final_action,
        "risk_thesis_invalidated": thesis_invalidated,
        "risk_overrode_action": original_action != final_action,
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
