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


def _format_risk_debate_for_judge(state: dict) -> str:
    """
    Provide explicit Stage C/D risk debate outputs to the Risk Manager judge.
    """
    risk_state = state.get("risk_debate_state", {}) or {}
    aggressive = (risk_state.get("aggressive_history") or "").strip()
    conservative = (risk_state.get("conservative_history") or "").strip()
    neutral = (risk_state.get("neutral_history") or "").strip()
    history = (risk_state.get("history") or "").strip()

    lines = [
        "**RISK DEBATE OUTPUTS**",
        f"- Exchanges: {risk_state.get('count', 0)}",
        f"- Latest speaker: {risk_state.get('latest_speaker', 'N/A')}",
        "",
        "Aggressive Risk Analyst:",
        aggressive if aggressive else "N/A",
        "",
        "Conservative Risk Analyst:",
        conservative if conservative else "N/A",
        "",
        "Neutral Risk Analyst:",
        neutral if neutral else "N/A",
    ]

    # Keep a concise fallback when role-specific fields are unexpectedly missing.
    if not aggressive and not conservative and not neutral and history:
        lines.extend(["", "Debate History (fallback):", history])

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
    Task: identify the strongest evidence that the proposed thesis can survive this horizon.

    Trader action: {action}
    Research Manager action: {rm_action}
    {disagreement_note}
    Market Context: VIX={volatility_index}, TickerRisk={ticker_risk}
    Analyst Evidence:
    {_format_reports_for_risk_debate(state)}
    Strategy:
    {strategy}

    Use only provided context. No outside facts.
    Be evidence-led, not directional cheerleading.

    Output:
    - THESIS_SURVIVAL_CLAIM: 1 line
    - STRONGEST_SUPPORT_EVIDENCE: 1 bullet (specific evidence and why it supports survival)
    - STRONGEST_BREAKER_ACKNOWLEDGED: 1 bullet
    - BREAKER_STRENGTH: LOW | MEDIUM | HIGH
    - HORIZON_RELEVANCE: YES | NO
    - SURVIVAL_CONFIDENCE: LOW | MEDIUM | HIGH

    Keep under 160 words. Start with "Aggressive Analyst:"."""
    else:
        # Subsequent rounds - respond to other analysts
        prompt = f"""Role: Risk Analyst A in debate for {ticker}.
    Task: reassess whether the thesis can still survive after opposing evidence.

    Strategy: {action}
    Market: VIX={volatility_index}, Risk={ticker_risk}
    Evidence:
    {_format_reports_for_risk_debate(state)}
    Conservative view:
    {conservative_last if conservative_last else "N/A"}
    Neutral view:
    {neutral_last if neutral_last else "N/A"}

    Use only provided context.
    Round-2 discipline: output only new evidence, explicit concessions, or confidence updates.
    Do not restate your round-1 points unless they materially changed.
    Do not force disagreement. If the breaker is now stronger, concede explicitly.

    Output:
    - REASSESSMENT: 1 line
    - UPDATED_STRONGEST_SUPPORT_EVIDENCE: 1 bullet
    - UPDATED_STRONGEST_BREAKER_ACKNOWLEDGED: 1 bullet
    - UPDATED_BREAKER_STRENGTH: LOW | MEDIUM | HIGH
    - UPDATED_HORIZON_RELEVANCE: YES | NO
    - UPDATED_SURVIVAL_CONFIDENCE: LOW | MEDIUM | HIGH

    Keep under 150 words. Start with "Aggressive Analyst:"."""
    
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
    Task: identify the single strongest evidence-based thesis breaker for this horizon.

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
    Be critical but fair: include the strongest refutation to your breaker.

    Output:
    - THESIS_BREAKER: 1 line
    - BREAKER_EVIDENCE: 1 bullet (specific evidence -> break mechanism)
    - BEST_REFUTATION_TO_BREAKER: 1 bullet
    - BREAKER_STRENGTH: LOW | MEDIUM | HIGH
    - HORIZON_RELEVANCE: YES | NO
    - BREAKER_CONFIDENCE: LOW | MEDIUM | HIGH

    Keep under 160 words. Start with "Conservative Analyst:"."""
    else:
        # Subsequent rounds
        prompt = f"""Role: Risk Analyst B in debate for {ticker}.
    Task: re-evaluate the strongest thesis breaker after reviewing other views.

    Strategy: {action}
    Market: VIX={volatility_index}, Risk={ticker_risk}
    Evidence:
    {_format_reports_for_risk_debate(state)}
    Aggressive view:
    {aggressive_last if aggressive_last else "N/A"}
    Neutral view:
    {neutral_last if neutral_last else "N/A"}

    Use only provided context.
    Round-2 discipline: output only new breaker evidence, explicit concessions, or confidence updates.
    Do not restate your round-1 points unless they materially changed.
    Do not force disagreement. If your breaker is no longer strongest, downgrade it.

    Output:
    - REASSESSMENT: 1 line
    - UPDATED_THESIS_BREAKER: 1 line
    - UPDATED_BREAKER_EVIDENCE: 1 bullet
    - UPDATED_BEST_REFUTATION_TO_BREAKER: 1 bullet
    - UPDATED_BREAKER_STRENGTH: LOW | MEDIUM | HIGH
    - UPDATED_HORIZON_RELEVANCE: YES | NO
    - UPDATED_BREAKER_CONFIDENCE: LOW | MEDIUM | HIGH

    Keep under 150 words. Start with "Conservative Analyst:"."""
    
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
Task: adjudicate which side has stronger evidence for this horizon. Do not output a trade recommendation.

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
Do not split the difference by default.
Pick a winner (SURVIVAL or BREAKER) unless evidence is genuinely tied.
Name one decisive evidence conflict that determined your winner.

Output:
- WINNING_SIDE: SURVIVAL | BREAKER | TIED
- DECISIVE_EVIDENCE_CONFLICT: 1 line
- STRONGEST_SURVIVAL_EVIDENCE: 1 bullet
- STRONGEST_BREAKER_EVIDENCE: 1 bullet
- UNREFUTED_HIGH_STRENGTH_BREAKER: YES | NO
- THESIS_STATUS: VALID | INVALID | UNCERTAIN
- EXECUTION_FRAGILITY_VIEW: LOW | HIGH | N/A
- WHAT_NEW_EVIDENCE_WOULD_FLIP_DECISION: 1 bullet

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

class RiskManagerDecisionDebate(BaseModel):
    thesis_validity: Literal["VALID", "INVALID", "UNCERTAIN"]
    execution_fragility: Literal["LOW", "HIGH", "N/A"]
    risk_judgment: Literal["CLEAR", "REDUCE", "BLOCK"]
    rationale: str
    position_size_pct: float = Field(ge=0, le=100)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class RiskManagerDecisionSingle(BaseModel):
    risk_judgment: Literal["CLEAR", "REDUCE", "BLOCK"]
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

    # Prior provenance from Stage B manager (anchored to Stage A-equivalent view).
    # This is context for risk adjudication only, not a separate decision source.
    investment_plan_structured = state.get("investment_plan_structured", {}) or {}
    prior_view = investment_plan_structured.get("prior_view", "UNKNOWN")
    prior_confirmed = investment_plan_structured.get("prior_confirmed", "UNKNOWN")
    override_reason = investment_plan_structured.get("override_reason", "")

    disagreement_context = ""
    if research_manager_action != "UNKNOWN" and research_manager_action != trader_action:
        disagreement_context = f"""\n⚠️ DISAGREEMENT: Research Manager recommended {research_manager_action}, Trader chose {trader_action}.
Decide which side has stronger evidence for the next {horizon_days} trading days.\n"""
    else:
        disagreement_context = f"\n✅ No major disagreement: current directional action is {trader_action}.\n"

    risk_mode = (run_config.get("risk_mode", "single") or "single").lower()

    if risk_mode == "debate":
        prompt = f"""Role: Risk Manager (Debate Judge).
Task: Judge whether the proposed action thesis remains valid for the next {horizon_days} trading days for {ticker}.
Your objective is risk falsification after considering all three risk analysts, not re-predicting direction from scratch.

Proposed Action: {trader_action}
Research Manager Action: {research_manager_action}
Trader Action: {trader_action}
Disagreement Context: {disagreement_context.strip()}
Prior Provenance:
- VIEW: {prior_view}
- PRIOR_CONFIRMED: {prior_confirmed}
- OVERRIDE REASON: {override_reason or 'N/A'}
Strategy Details: {strategy}

Analyst Evidence:
{_format_reports_for_risk_debate(state)}

Risk Debate Evidence:
{_format_risk_debate_for_judge(state)}

Market Context:
- VIX: {volatility_index}
- Ticker Risk: {ticker_risk}

Use only the provided evidence.

Falsification Protocol:
1) Extract the single strongest thesis breaker and its strength from the debate.
2) Decide whether that breaker is still unrefuted at this horizon.
3) Then decide THESIS_VALIDITY and EXECUTION_FRAGILITY.

Two-gate decision:
- Gate A (validity): for BUY/SELL, if THESIS_VALIDITY is INVALID or UNCERTAIN, default to BLOCK.
- Gate B (path): if THESIS_VALIDITY is VALID, use EXECUTION_FRAGILITY to choose CLEAR (LOW) or REDUCE (HIGH).

HOLD handling:
- For Proposed Action HOLD, default CLEAR unless evidence strongly implies a directional trade should be taken now.

Calibration:
- REDUCE is allowed only when you can name a concrete execution-path fragility mechanism while thesis validity remains VALID.
- REDUCE is not allowed for general uncertainty or mixed evidence; those map to Gate A and therefore BLOCK for BUY/SELL.
- BLOCK requires a clear explanation of why the strongest breaker remains unresolved at this horizon.

Output format:
THESIS_VALIDITY: VALID|INVALID|UNCERTAIN
EXECUTION_FRAGILITY: LOW|HIGH|N/A
RISK_JUDGMENT: CLEAR|REDUCE|BLOCK
RATIONALE:
- 2-4 sentences with: strongest breaker, strongest refutation, and why the selected judgment follows the two-gate decision.
- If RISK_JUDGMENT=REDUCE, explicitly include "FRAGILITY_MECHANISM:" and one concrete mechanism.
ADJUSTMENTS:
- Position Size: [X%] (0 if BLOCK)
- Stop Loss: [price|null]
- Take Profit: [price|null]

Keep under 220 words."""
        structured_prompt = prompt + """

Return strict JSON with keys:
thesis_validity, execution_fragility, risk_judgment, rationale, position_size_pct, stop_loss, take_profit
"""
        decision_model = RiskManagerDecisionDebate
    else:
        prompt = f"""Role: Risk Manager.
Task: Assess whether the proposed action thesis remains valid for the next {horizon_days} trading days for {ticker}.
Your objective is risk falsification, not re-predicting direction from scratch.

Proposed Action: {trader_action}
Disagreement Context: {disagreement_context.strip()}
Prior Provenance:
- VIEW: {prior_view}
- PRIOR_CONFIRMED: {prior_confirmed}
- OVERRIDE REASON: {override_reason or 'N/A'}
Strategy Details: {strategy}

Analyst Evidence:
{_format_reports_for_risk_debate(state)}

Market Context:
- VIX: {volatility_index}
- Ticker Risk: {ticker_risk}

Use only the provided evidence.

Decision Intent Framework (Choose ONE):
1. CLEAR: The proposed {trader_action} thesis survives scrutiny. Volatility and risk factors are acceptable. Normal sizing.
2. REDUCE: The {trader_action} thesis survives, but faces elevated uncertainty, conflicting secondary signals, or provenance fragility. Maintain direction but shrink position size significantly.
3. BLOCK: The {trader_action} thesis is structurally broken by extreme market risk or undeniable contradictory evidence. VETO the trade (forces HOLD). Make this rare and strictly evidence-anchored.

Output format:
RISK_JUDGMENT: CLEAR|REDUCE|BLOCK
RATIONALE:
- 2-4 sentences explaining why the trade was cleared, reduced, or blocked.
ADJUSTMENTS:
- Position Size: [X%] (0 if BLOCK)
- Stop Loss: [price|null]
- Take Profit: [price|null]

Keep under 200 words."""
        structured_prompt = prompt + """

Return strict JSON with keys:
risk_judgment, rationale, position_size_pct, stop_loss, take_profit
"""
        decision_model = RiskManagerDecisionSingle

    try:
        decision = call_llm_structured(
            structured_prompt,
            decision_model,
            temperature=0.2,
        )
    except Exception as e:
        if risk_mode == "debate":
            # On parser failure in debate mode, preserve safety semantics:
            # directional actions -> BLOCK, HOLD -> CLEAR.
            fallback_judgment = "CLEAR" if trader_action == "HOLD" else "BLOCK"
            decision = RiskManagerDecisionDebate(
                thesis_validity="UNCERTAIN",
                execution_fragility="N/A",
                risk_judgment=fallback_judgment,
                rationale=f"Structured output failure: {e}. Fallback to {fallback_judgment} used due to unresolved thesis validity.",
                position_size_pct=0,
                stop_loss=None,
                take_profit=None,
            )
        else:
            # Restore historical B+ fallback behavior to avoid accidental vetoes.
            decision = RiskManagerDecisionSingle(
                risk_judgment="CLEAR",
                rationale=f"Structured output failure: {e}. Fallback to CLEAR used.",
                position_size_pct=0 if trader_action == "HOLD" else 10,
                stop_loss=None,
                take_profit=None,
            )

    # Minimal consistency guardrail for directional actions.
    # LLM still decides thesis validity and fragility; this prevents invalid mapping drift.
    if risk_mode == "debate" and trader_action in {"BUY", "SELL"} and decision.thesis_validity in {"INVALID", "UNCERTAIN"}:
        if decision.risk_judgment != "BLOCK":
            decision.risk_judgment = "BLOCK"
            decision.position_size_pct = 0
            decision.execution_fragility = "N/A"
            decision.rationale = (
                "Consistency override: directional trade marked INVALID/UNCERTAIN must be BLOCK. "
                + (decision.rationale or "")
            ).strip()

    final_decision_json = decision.model_dump_json(indent=2)
    risk_judgment = decision.risk_judgment

    # Map the risk judgment back to an action
    if risk_judgment == "BLOCK":
        final_action = "HOLD"
    else:
        final_action = trader_action

    strategy["action"] = final_action
    strategy["rationale"] = f"[{risk_judgment}] {decision.rationale}"

    if final_action != "HOLD":
        risk_rating = (ticker_risk.get("risk_rating") or "MODERATE").upper()
        max_position_pct = 8 if risk_rating == "HIGH" else 15 if risk_rating == "MODERATE" else 25

        old_position = strategy.get("position_size_pct", 0) or 0
        model_position = float(decision.position_size_pct or 0)
        requested_position = model_position if model_position > 0 else float(old_position)
        new_position = min(float(requested_position), float(max_position_pct)) if requested_position else float(max_position_pct)
        
        # Keep REDUCE meaningful without collapsing into near-zero exposure by default.
        if risk_judgment == "REDUCE":
            reduce_cap = max(6.0, float(max_position_pct) * 0.5)
            new_position = min(new_position, reduce_cap)

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
    state['risk_reports']['risk_manager_decision'] = final_decision_json
    risk_gate_prefix = "Risk debate judged" if risk_mode == "debate" else "Single risk-check evaluated"
    state['risk_reports']['risk_gate'] = f"{risk_gate_prefix}. Original: {original_action}, Judgment: {risk_judgment}, Final: {final_action}"

    if 'run_metadata' not in state:
        state['run_metadata'] = {}
    thesis_validity_meta = decision.thesis_validity if hasattr(decision, "thesis_validity") else "N/A"
    execution_fragility_meta = decision.execution_fragility if hasattr(decision, "execution_fragility") else "N/A"
    state['run_metadata'].update({
        "risk_original_action": original_action,
        "risk_final_action": final_action,
        "risk_mode": risk_mode,
        "risk_judgment": risk_judgment,
        "risk_thesis_validity": thesis_validity_meta,
        "risk_execution_fragility": execution_fragility_meta,
        "risk_overrode_action": original_action != final_action,
    })

    return state


