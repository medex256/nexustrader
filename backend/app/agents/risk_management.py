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


def _extract_risk_vote(response: str) -> dict:
    """Parse tribunal vote fields from a risk analyst response."""
    text = response or ""

    def pick(pattern: str, default: str = "N/A") -> str:
        m = re.search(pattern, text, re.IGNORECASE)
        return (m.group(1).strip() if m else default)

    vote = pick(r"(?:^|\n)\s*-\s*(?:UPDATED_)?VOTE\s*:\s*(BLOCK|REDUCE|CLEAR)")
    unresolved_breaker = pick(r"(?:^|\n)\s*-\s*(?:UPDATED_)?UNRESOLVED_BREAKER\s*:\s*(.+)")
    breaker_strength = pick(r"(?:^|\n)\s*-\s*(?:UPDATED_)?BREAKER_STRENGTH\s*:\s*(LOW|MEDIUM|HIGH)")
    horizon_relevance = pick(r"(?:^|\n)\s*-\s*(?:UPDATED_)?HORIZON_RELEVANCE\s*:\s*(YES|NO)")
    novelty = pick(r"(?:^|\n)\s*-\s*(?:UPDATED_)?NOVELTY_VS_UPSTREAM\s*:\s*(NEW|ALREADY_KNOWN)")
    veto_confidence = pick(r"(?:^|\n)\s*-\s*(?:UPDATED_)?VETO_CONFIDENCE\s*:\s*(LOW|MEDIUM|HIGH)")
    confidence = pick(r"(?:^|\n)\s*-\s*(?:UPDATED_)?CONFIDENCE\s*:\s*(LOW|MEDIUM|HIGH)")

    return {
        "vote": vote.upper() if vote != "N/A" else "N/A",
        "unresolved_breaker": unresolved_breaker,
        "breaker_strength": breaker_strength.upper() if breaker_strength != "N/A" else "N/A",
        "horizon_relevance": horizon_relevance.upper() if horizon_relevance != "N/A" else "N/A",
        "novelty": novelty.upper() if novelty != "N/A" else "N/A",
        "veto_confidence": veto_confidence.upper() if veto_confidence != "N/A" else "N/A",
        "confidence": confidence.upper() if confidence != "N/A" else "N/A",
    }


def _format_risk_votes_for_judge(state: dict) -> str:
    """Create a compact tribunal table for the risk judge prompt."""
    risk_state = state.get("risk_debate_state", {}) or {}
    votes = risk_state.get("votes", {}) or {}

    rows = []
    for role_key, role_name in [
        ("aggressive", "Aggressive"),
        ("conservative", "Conservative"),
        ("neutral", "Neutral"),
    ]:
        v = votes.get(role_key, {}) or {}
        rows.append(
            f"- {role_name}: VOTE={v.get('vote', 'N/A')}, "
            f"BREAKER_STRENGTH={v.get('breaker_strength', 'N/A')}, "
            f"HORIZON_RELEVANCE={v.get('horizon_relevance', 'N/A')}, "
            f"NOVELTY={v.get('novelty', 'N/A')}, "
            f"VETO_CONFIDENCE={v.get('veto_confidence', 'N/A')}, "
            f"CONFIDENCE={v.get('confidence', 'N/A')}, "
            f"UNRESOLVED_BREAKER={v.get('unresolved_breaker', 'N/A')}"
        )

    vote_values = [str((votes.get(k, {}) or {}).get("vote", "")).upper() for k in ("aggressive", "conservative", "neutral")]
    block_n = sum(1 for x in vote_values if x == "BLOCK")
    reduce_n = sum(1 for x in vote_values if x == "REDUCE")
    clear_n = sum(1 for x in vote_values if x == "CLEAR")

    header = [
        "**RISK TRIBUNAL VOTES**",
        f"- Vote counts: BLOCK={block_n}, REDUCE={reduce_n}, CLEAR={clear_n}",
    ]
    return "\n".join(header + rows)

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
            'votes': {},
            'latest_speaker': '',
            'count': 0,
        }
    
    debate_state = state['risk_debate_state']
    debate_state.setdefault('votes', {})
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
    
    # Build lean prompt (Stage C/D only; B/B+ paths are unaffected)
    if debate_state['count'] == 0:
        prompt = f"""Role: Aggressive Risk Analyst for {ticker}.
    Task: build the strongest evidence-based rescue case for the proposed thesis at this horizon.
    You are not allowed to ignore breakers; your job is to test whether a credible survival path exists.

Proposed Action: {action}
Research Manager Action: {rm_action}
{disagreement_note}
Market Context: VIX={volatility_index}, TickerRisk={ticker_risk}
Analyst Evidence:
{_format_reports_for_risk_debate(state)}
Strategy Context:
{strategy}

Return concise text in this exact format:
Aggressive Analyst:
- THESIS_SURVIVAL_CLAIM: <1 line>
- RESCUE_MECHANISM_WITHIN_HORIZON: <1 line>
- UNRESOLVED_BREAKER: <1 line>
- BREAKER_STRENGTH: LOW | MEDIUM | HIGH
- HORIZON_RELEVANCE: YES | NO
- VOTE: BLOCK | REDUCE | CLEAR
- NOVELTY_VS_UPSTREAM: NEW | ALREADY_KNOWN
- VETO_CONFIDENCE: LOW | MEDIUM | HIGH
- CONFIDENCE: LOW | MEDIUM | HIGH

Calibration:
- If no credible rescue mechanism exists within horizon, do not force optimism.
- BLOCK is valid when breaker cannot be neutralized by concrete near-term evidence.

Keep under 130 words."""
    else:
        prompt = f"""Role: Aggressive Risk Analyst for {ticker}.
    Task: update your rescue-case assessment after reviewing opposing arguments.
    Use only provided context.

Proposed Action: {action}
Market Context: VIX={volatility_index}, Risk={ticker_risk}
Analyst Evidence:
{_format_reports_for_risk_debate(state)}
Conservative view:
{conservative_last if conservative_last else "N/A"}
Neutral view:
{neutral_last if neutral_last else "N/A"}

Round-2 discipline:
- Output only updates, concessions, or confidence changes.
- Do not repeat unchanged points.

Return concise text in this exact format:
Aggressive Analyst:
- UPDATED_THESIS_SURVIVAL_CLAIM: <1 line>
- UPDATED_RESCUE_MECHANISM_WITHIN_HORIZON: <1 line>
- UPDATED_UNRESOLVED_BREAKER: <1 line>
- UPDATED_BREAKER_STRENGTH: LOW | MEDIUM | HIGH
- UPDATED_HORIZON_RELEVANCE: YES | NO
- UPDATED_VOTE: BLOCK | REDUCE | CLEAR
- UPDATED_NOVELTY_VS_UPSTREAM: NEW | ALREADY_KNOWN
- UPDATED_VETO_CONFIDENCE: LOW | MEDIUM | HIGH
- UPDATED_CONFIDENCE: LOW | MEDIUM | HIGH

Keep under 120 words."""
    
    # Generate response
    response = call_llm(prompt)
    
    # Update debate state
    debate_state['aggressive_history'] += f"\n\n{response}"
    debate_state['history'] += f"\n\n{response}"
    debate_state.setdefault('votes', {})['aggressive'] = _extract_risk_vote(response)
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
    debate_state.setdefault('votes', {})
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
    
    # Build lean prompt (Stage C/D only; B/B+ paths are unaffected)
    if debate_state['count'] == 1:
        prompt = f"""Role: Conservative Risk Analyst for {ticker}.
    Task: act as the committee falsifier and identify whether this thesis should be vetoed at this horizon.
    Do not re-predict direction. Use only provided evidence.

Proposed Action: {action}
Research Manager Action: {rm_action}
{disagreement_note}
Market Context: VIX={volatility_index}, TickerRisk={ticker_risk}
Analyst Evidence:
{_format_reports_for_risk_debate(state)}
Strategy Context:
{strategy}
Aggressive view:
{aggressive_last if aggressive_last else "N/A"}

Return concise text in this exact format:
Conservative Analyst:
- THESIS_BREAKER: <1 line>
- FALSIFICATION_TRIGGER: <1 line condition that would force BLOCK>
- UNRESOLVED_BREAKER: <1 line>
- BREAKER_STRENGTH: LOW | MEDIUM | HIGH
- HORIZON_RELEVANCE: YES | NO
- VOTE: BLOCK | REDUCE | CLEAR
- NOVELTY_VS_UPSTREAM: NEW | ALREADY_KNOWN
- VETO_CONFIDENCE: LOW | MEDIUM | HIGH
- CONFIDENCE: LOW | MEDIUM | HIGH

Calibration:
- Be strict on unresolved high-impact breakers.
- If breaker is HIGH and horizon-relevant with weak refutation, prefer BLOCK.

Keep under 130 words."""
    else:
        prompt = f"""Role: Conservative Risk Analyst for {ticker}.
    Task: update your falsification assessment after reviewing other views.
    Use only provided context.

Proposed Action: {action}
Market Context: VIX={volatility_index}, Risk={ticker_risk}
Analyst Evidence:
{_format_reports_for_risk_debate(state)}
Aggressive view:
{aggressive_last if aggressive_last else "N/A"}
Neutral view:
{neutral_last if neutral_last else "N/A"}

Round-2 discipline:
- Output only updates, concessions, or confidence changes.
- Do not repeat unchanged points.

Return concise text in this exact format:
Conservative Analyst:
- UPDATED_THESIS_BREAKER: <1 line>
- UPDATED_FALSIFICATION_TRIGGER: <1 line>
- UPDATED_UNRESOLVED_BREAKER: <1 line>
- UPDATED_BREAKER_STRENGTH: LOW | MEDIUM | HIGH
- UPDATED_HORIZON_RELEVANCE: YES | NO
- UPDATED_VOTE: BLOCK | REDUCE | CLEAR
- UPDATED_NOVELTY_VS_UPSTREAM: NEW | ALREADY_KNOWN
- UPDATED_VETO_CONFIDENCE: LOW | MEDIUM | HIGH
- UPDATED_CONFIDENCE: LOW | MEDIUM | HIGH

Keep under 120 words."""
    
    # Generate response
    response = call_llm(prompt)
    
    # Update debate state
    debate_state['conservative_history'] += f"\n\n{response}"
    debate_state['history'] += f"\n\n{response}"
    debate_state.setdefault('votes', {})['conservative'] = _extract_risk_vote(response)
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
    debate_state.setdefault('votes', {})
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
    
    # Build lean prompt (Stage C/D only; B/B+ paths are unaffected)
    prompt = f"""Role: Neutral Risk Analyst for {ticker}.
Task: act as evidence-integrity auditor and resolve the committee disagreement.
Do not output BUY/SELL/HOLD. Use only provided context.

Proposed Action: {action}
Research Manager Action: {rm_action}
{disagreement_note}
Market Context: VIX={volatility_index}, TickerRisk={ticker_risk}
Analyst Evidence:
{_format_reports_for_risk_debate(state)}
Strategy Context:
{strategy}
Aggressive view:
{aggressive_last if aggressive_last else "N/A"}
Conservative view:
{conservative_last if conservative_last else "N/A"}

Return concise text in this exact format:
Neutral Analyst:
- WINNING_SIDE: SURVIVAL | BREAKER | TIED
- THESIS_STATUS: VALID | INVALID | UNCERTAIN
- EXECUTION_FRAGILITY_VIEW: LOW | HIGH | N/A
- UNRESOLVED_BREAKER: <1 line>
- BREAKER_STRENGTH: LOW | MEDIUM | HIGH
- HORIZON_RELEVANCE: YES | NO
- VOTE: BLOCK | REDUCE | CLEAR
- NOVELTY_VS_UPSTREAM: NEW | ALREADY_KNOWN
- VETO_CONFIDENCE: LOW | MEDIUM | HIGH
- CONFIDENCE: LOW | MEDIUM | HIGH

Calibration:
- Do not split by default.
- Use TIED only when evidence is genuinely balanced.
- If THESIS_STATUS is INVALID or UNCERTAIN with unresolved HIGH breaker, VOTE should generally be BLOCK.

Keep under 140 words."""
    
    # Generate response
    response = call_llm(prompt)
    
    # Update debate state
    debate_state['neutral_history'] += f"\n\n{response}"
    debate_state['history'] += f"\n\n{response}"
    debate_state.setdefault('votes', {})['neutral'] = _extract_risk_vote(response)
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
Task: choose final risk judgment for the proposed action over the next {horizon_days} trading days for {ticker}.
Your job is thesis stress-testing, not direction re-forecasting.

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

Risk Tribunal Vote Table:
{_format_risk_votes_for_judge(state)}

Market Context:
- VIX: {volatility_index}
- Ticker Risk: {ticker_risk}

Use only provided evidence.

Decision policy (soft rubric, not a hard rule):
Decision ladder:
1) Falsification first:
    - If THESIS_VALIDITY=INVALID for BUY/SELL, choose BLOCK unless you explicitly refute the strongest breaker.
    - If THESIS_VALIDITY=UNCERTAIN and unresolved breaker is HIGH + horizon-relevant, choose BLOCK unless refuted.
2) If thesis survives:
    - Choose REDUCE only when fragility is concrete and near-term.
    - Choose CLEAR when fragility is weak, refuted, or already priced.
3) Tribunal signal integration:
    - Treat 2+ BLOCK votes with HIGH breaker strength, HORIZON_RELEVANCE=YES, and at least one HIGH VETO_CONFIDENCE as strong evidence, not a hard rule.
4) HOLD semantics:
    - For HOLD proposals, do not use BLOCK; choose CLEAR or REDUCE.

Calibration:
- Do not BLOCK from vague uncertainty alone.
- Do not use REDUCE as a default safe option.
- If BLOCK, state whether the breaker is NEW versus ALREADY_KNOWN upstream.

Output format:
THESIS_VALIDITY: VALID|INVALID|UNCERTAIN
EXECUTION_FRAGILITY: LOW|HIGH|N/A
RISK_JUDGMENT: CLEAR|REDUCE|BLOCK
RATIONALE:
- 2-3 sentences with strongest breaker, strongest refutation, and why the final judgment is calibrated.
- If RISK_JUDGMENT=REDUCE, include "FRAGILITY_MECHANISM:" and one concrete mechanism.
- If RISK_JUDGMENT=REDUCE, include "WHY_NOT_BLOCK:" with one evidence-based sentence.
- If RISK_JUDGMENT=BLOCK, include "NOVEL_BREAKER:" as NEW or ALREADY_KNOWN.
ADJUSTMENTS:
- Position Size: [X%] (0 if BLOCK)
- Stop Loss: [price|null]
- Take Profit: [price|null]

Keep under 190 words."""
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

    consistency_repair_applied = False
    hold_block_adjusted = False

    # Repair directional inconsistency via a short second-pass LLM check.
    if (
        risk_mode == "debate"
        and trader_action in {"BUY", "SELL"}
        and getattr(decision, "thesis_validity", "VALID") in {"INVALID", "UNCERTAIN"}
        and decision.risk_judgment != "BLOCK"
    ):
        repair_prompt = f"""Role: Risk Manager Consistency Repair.
You must repair an internally inconsistent prior decision for a directional proposal.

Directional proposal: {trader_action}
Prior decision JSON:
{decision.model_dump_json(indent=2)}

Policy:
- If THESIS_VALIDITY is INVALID or UNCERTAIN for BUY/SELL, BLOCK is the default unless you can justify THESIS_VALIDITY=VALID.
- Do not invent new evidence. Only repair logical consistency.

Return strict JSON with keys:
thesis_validity, execution_fragility, risk_judgment, rationale, position_size_pct, stop_loss, take_profit
"""
        try:
            repaired = call_llm_structured(
                repair_prompt,
                RiskManagerDecisionDebate,
                temperature=0.1,
            )
            decision = repaired
            consistency_repair_applied = True
        except Exception:
            # Keep original decision if repair fails; diagnostics will still flag inconsistency.
            pass

    # HOLD cannot be meaningfully blocked because final action remains HOLD.
    if risk_mode == "debate" and trader_action == "HOLD" and decision.risk_judgment == "BLOCK":
        decision.risk_judgment = "CLEAR"
        decision.rationale = (
            f"{decision.rationale} HOLD normalization applied: BLOCK converted to CLEAR."
        )
        hold_block_adjusted = True

    # Track gate consistency as diagnostics for calibration analysis.
    gate_inconsistent = (
        risk_mode == "debate"
        and trader_action in {"BUY", "SELL"}
        and getattr(decision, "thesis_validity", "VALID") in {"INVALID", "UNCERTAIN"}
        and decision.risk_judgment != "BLOCK"
    )

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
    vote_state = (state.get("risk_debate_state", {}) or {}).get("votes", {}) or {}
    vote_values = [str((vote_state.get(k, {}) or {}).get("vote", "")).upper() for k in ("aggressive", "conservative", "neutral")]
    vote_block_n = sum(1 for x in vote_values if x == "BLOCK")
    vote_reduce_n = sum(1 for x in vote_values if x == "REDUCE")
    vote_clear_n = sum(1 for x in vote_values if x == "CLEAR")
    thesis_validity_meta = decision.thesis_validity if hasattr(decision, "thesis_validity") else "N/A"
    execution_fragility_meta = decision.execution_fragility if hasattr(decision, "execution_fragility") else "N/A"
    state['run_metadata'].update({
        "risk_original_action": original_action,
        "risk_final_action": final_action,
        "risk_mode": risk_mode,
        "risk_judgment": risk_judgment,
        "risk_thesis_validity": thesis_validity_meta,
        "risk_execution_fragility": execution_fragility_meta,
        "risk_vote_block_n": vote_block_n,
        "risk_vote_reduce_n": vote_reduce_n,
        "risk_vote_clear_n": vote_clear_n,
        "risk_gate_inconsistent": bool(gate_inconsistent),
        "risk_consistency_repair_applied": bool(consistency_repair_applied),
        "risk_hold_block_adjusted": bool(hold_block_adjusted),
        "risk_overrode_action": original_action != final_action,
    })

    return state


