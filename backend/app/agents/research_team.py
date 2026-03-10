# In nexustrader/backend/app/agents/research_team.py

import json
from typing import Literal
from pydantic import BaseModel, Field

from ..llm import invoke_llm as call_llm
from ..llm import invoke_llm_structured as call_llm_structured
from ..utils.memory import get_memory


class StageAManagerDecision(BaseModel):
    """
    Stage A schema — minimal, clean.
    The LLM reasons freely over prose reports and outputs a direction.
    No scoring fields, no vote/strength labels — those only exist to feed
    rule-based scorers, which Stage A deliberately avoids.
    """
    recommendation: Literal["BUY", "SELL", "HOLD"] = "HOLD"
    confidence_score: float = Field(default=0.5, ge=0, le=1)
    primary_drivers: list[str] = Field(default_factory=list)
    main_risk: str = "Unknown"


class ResearchManagerDecision(BaseModel):
    """
    Debate-stage schema (B / B+ / C / D).
    buy_score / sell_score are descriptive metadata only for B/B+
    (UI gauges, calibration).  The spread rule is applied only for C/D.
    For B/B+ the LLM's holistic recommendation field is the decision.

    v6 fields: prior_view / prior_confirmed / override_reason capture the
    anchored-prior chain.  Downstream stages (B+, C) use these for provenance-
    aware risk gating.
    """
    buy_score: float = Field(
        ge=0, le=10,
        description="Upside evidence strength 0-10. Score the active bullish evidence."
    )
    sell_score: float = Field(
        ge=0, le=10,
        description="Downside evidence strength 0-10. Score the active bearish evidence."
    )
    recommendation: Literal["BUY", "SELL", "HOLD"]
    confidence_score: float = Field(ge=0, le=1)
    primary_drivers: list[str] = Field(
        description="List of 1-3 specific evidence items that most strongly drove the recommendation."
    )
    main_risk: str = Field(
        description="The single most important named risk to the chosen direction."
    )
    # --- v6 anchored-prior provenance ---
    prior_view: str = "HOLD"  # Stage A-equivalent decision before specialists ran
    prior_confirmed: bool = True  # True if output matches prior_view
    override_reason: str = ""  # Non-empty only when prior_confirmed=False
    # --- legacy fields (kept for backwards-compat with scoring scripts) ---
    base_view_from_reports: Literal["BUY", "SELL", "HOLD"] = "HOLD"
    base_view_rationale: str = "Unknown"
    upside_note_impact: str = "Unknown"
    downside_note_impact: str = "Unknown"
    actionability_assessment: str = "Unknown"
    hold_gate_assessment: str = "Unknown"
    execution_notes: list[str] = Field(default_factory=list)


def _band_from_score(score: float) -> str:
    if score >= 0.75:
        return "HIGH"
    if score >= 0.45:
        return "MEDIUM"
    return "LOW"


def _format_signal_summary_for_debate(state: dict) -> str:
    """
    Signal-only summary for debaters.
    This intentionally excludes long prose analyst reports to prevent signal dilution.
    """
    signals = state.get('signals', {})
    lines = ["**ANALYST SIGNAL SUMMARY (DEBATE INPUT)**"]
    for key, label in [('fundamental', 'Fundamental'), ('technical', 'Technical'), ('news', 'News/Sentiment')]:
        if key in signals:
            s = signals[key]
            lines.append(
                f"- **{label}**: {s.get('direction', 'N/A')} "
                f"| magnitude={s.get('magnitude', 0.0):.2f} "
                f"| confidence={s.get('confidence', 0.5):.2f} "
                f"| key_catalyst={s.get('key_catalyst', 'UNKNOWN')} "
                f"| primary_risk={s.get('primary_risk', 'UNKNOWN')}"
            )
        else:
            lines.append(f"- **{label}**: No signal available")

    return "\n".join(lines)


def _format_reports_for_judge(state: dict) -> str:
    """
    Full analyst prose for the Research Manager only.
    """
    reports = state.get('reports', {})
    lines = ["**DETAILED ANALYST REPORTS (JUDGE CONTEXT)**"]
    for key, label in [
        ('fundamental_analyst', 'Fundamental Analysis'),
        ('technical_analyst', 'Technical Analysis'),
        ('news_harvester', 'News Analysis'),
    ]:
        if key in reports:
            lines.append(f"\n### {label}\n{reports[key]}")

    return "\n".join(lines)


def _is_single_extraction_mode(state: dict) -> bool:
    """
    Stage B / B+ use two non-adversarial specialist extractors instead of a mirrored bull/bear pair.
    Fall back to mode-based inference for custom runs that do not set an explicit stage.
    """
    run_config = state.get("run_config", {}) or {}
    stage = (run_config.get("stage") or "").strip().upper()
    if stage in {"B", "B+"}:
        return True
    if stage in {"C", "D"}:
        return False

    debate_mode = (run_config.get("debate_mode") or "on").strip().lower()
    debate_rounds = int(run_config.get("debate_rounds") or 0)
    risk_mode = (run_config.get("risk_mode") or "off").strip().lower()
    return debate_mode != "off" and debate_rounds > 0 and risk_mode in {"off", "single"}


def _get_stage_a_prior(state: dict, ticker: str, horizon_days: int) -> StageAManagerDecision:
    """
    Runs the Stage A (no-debate) manager prompt against the analyst reports to produce
    a committed prior direction before any specialist notes are injected.

    Called at the start of PATH B in research_manager_agent.  Adds one LLM call but
    zero topology change — it uses the same Stage A prompt logic PATH A uses.
    Returns StageAManagerDecision with recommendation, confidence_score, primary_drivers, main_risk.
    """
    prompt = f"""Role: Research Manager for {ticker}.
Task: synthesise the three analyst reports below and decide BUY, SELL, or HOLD
      for the next {horizon_days} trading days.

Read the full analyst reports. The signal summary is provided for quick reference,
but your reasoning must be grounded in the prose evidence, not just the labels.

Use HOLD only when you cannot determine which direction has materially stronger
evidence after reading the full reports. If one direction is supported by stronger
evidence — even if not unanimous — prefer that direction over HOLD.
Do not use HOLD as a safe default when evidence is mixed but one side is stronger.

Apply the same standard of evidence to BUY and SELL. Do not privilege either direction.

Signal Summary (quick reference):
{_format_signal_summary_for_debate(state)}

Full Analyst Reports:
{_format_reports_for_judge(state)}

Return JSON:
{{
  "recommendation": "BUY" | "SELL" | "HOLD",
  "confidence_score": <0.0 – 1.0>,
  "primary_drivers": ["<up to 3 key evidence items>"],
  "main_risk": "<single most important counterpoint>"
}}"""
    try:
        return call_llm_structured(prompt, StageAManagerDecision, temperature=0.2)
    except Exception:
        return StageAManagerDecision(
            recommendation="HOLD",
            confidence_score=0.35,
            primary_drivers=["Prior LLM call failed; fallback HOLD"],
            main_risk="Parse failure in _get_stage_a_prior",
        )


def _build_stage_b_manager_prompt(
    state: dict,
    ticker: str,
    horizon_days: int,
    upside_note: str,
    downside_note: str,
    prior_view: str = "HOLD",
) -> str:
    return f"""Role: Research Manager for {ticker}.
Task: decide BUY, SELL, or HOLD for the next {horizon_days} trading days.

You have a committed prior direction formed from the analyst reports alone, before any specialist
assessment. Start from this prior and change it only when the specialist evidence clears the bar below.

PRIOR VIEW: {prior_view}
(This is the direction the analyst reports alone support, before specialist notes.)

UPSIDE SPECIALIST ASSESSMENT:
{upside_note}

DOWNSIDE SPECIALIST ASSESSMENT:
{downside_note}

Full Analyst Reports (for verification):
{_format_reports_for_judge(state)}

DECISION PROTOCOL — apply in order, stop at the first rule that fires:
1. Read OVERRIDE_STRENGTH in the DOWNSIDE SPECIALIST ASSESSMENT.
2. If OVERRIDE_STRENGTH is NO_OVERRIDE → confirm prior unchanged. Set prior_confirmed=true.
3. If OVERRIDE_STRENGTH is REDUCE_CONFIDENCE and the cited risk is horizon-relevant and specific
   (not generic caution or valuation language) → keep prior direction, lower confidence by one
   level, set prior_confirmed=true.
4. If OVERRIDE_STRENGTH is OVERRIDE and the cited risk is materially stronger than the evidence
   that produced the prior AND has a clear transmission path within {horizon_days} days →
   change direction, set prior_confirmed=false, populate override_reason with the specific
   evidence cited by the downside analyst.
5. Use HOLD with prior_confirmed=false ONLY when step 4 override evidence creates genuine
   irresolvable uncertainty about direction (not merely cross-pressure between upside and
   downside notes).

Do NOT output HOLD because both notes raise valid points.
Do NOT override the prior for a risk that was already present in the analyst reports.
Do NOT treat REDUCE_CONFIDENCE as justification to flip direction.

REQUIRED field rules — do NOT leave these at defaults:
- primary_drivers: MUST contain 1-2 non-empty strings citing the specific evidence driving your decision.
- main_risk: MUST be a specific named risk, not 'Unknown'.
- buy_score: MUST reflect active upside evidence strength 0-10 (not 5.0 by default).
- sell_score: MUST reflect active downside evidence strength 0-10 (not 5.0 by default).

Return JSON:
{{
    "recommendation": "BUY" | "SELL" | "HOLD",
    "prior_view": "{prior_view}",
    "prior_confirmed": true | false,
    "override_reason": "<specific evidence from downside note that caused override, or empty string>",
    "confidence_score": <0.0 - 1.0>,
    "buy_score": <0-10, must reflect actual upside evidence strength>,
    "sell_score": <0-10, must reflect actual downside evidence strength>,
    "primary_drivers": ["<evidence item 1>", "<evidence item 2 if applicable>"],
    "main_risk": "<specific named risk — not Unknown>",
    "base_view_from_reports": "{prior_view}",
    "base_view_rationale": "<1 sentence: confirm prior or explain override>",
    "upside_note_impact": "<UPSIDE_STRENGTH value from upside note, or NO_NEW_UPSIDE>",
    "downside_note_impact": "<OVERRIDE_STRENGTH value from downside note>",
    "actionability_assessment": "<1 short sentence on which side has the clearer active near-term path>",
    "hold_gate_assessment": "<1 short sentence: is this genuine irresolvable uncertainty or background caution>"
}}"""


def _build_stage_cd_manager_prompt(
    state: dict,
    ticker: str,
    horizon_days: int,
    spread_threshold: float,
    debate_history: str,
) -> str:
    return f"""Role: Research Manager.
Task: choose BUY, SELL, or HOLD for {ticker} over the next {horizon_days} trading days.

Use only the evidence below. No external facts.
Apply symmetric criteria for BUY and SELL.

Scoring policy:
1) Score the BUY case from 0-10 using only concrete evidence in debate.
2) Score the SELL case from 0-10 using only concrete evidence in debate.
3) Decision rule:
   - BUY_SCORE - SELL_SCORE >= {spread_threshold:g} -> BUY
   - SELL_SCORE - BUY_SCORE >= {spread_threshold:g} -> SELL
   - Otherwise -> HOLD

Set confidence_score in [0, 1] as probability-like confidence for the chosen direction.

Primary driver rule:
- primary_drivers must include BOTH: 1-2 drivers supporting the chosen direction
  and 1 driver labeled "COUNTERPOINT:".
- main_risk must be the strongest counterpoint.

Signal Summary:
{_format_signal_summary_for_debate(state)}

Analyst Reports:
{_format_reports_for_judge(state)}

Debate:
{debate_history}

Return strict JSON matching schema fields:
buy_score, sell_score, recommendation, confidence_score, primary_drivers, main_risk, execution_notes."""


def bull_researcher_agent(state: dict):
    """
    Reused research-layer node.
    - Stage B / B+: Upside Catalyst Analyst (non-adversarial extractor)
    - Stage C / D: Bull Researcher in adversarial debate
    """
    reports = state.get('reports', {})
    ticker = state.get('ticker', '')
    
    # Initialize debate state if this is the first round
    if 'investment_debate_state' not in state or state['investment_debate_state'] is None:
        state['investment_debate_state'] = {
            'history': '',
            'bull_history': '',
            'bear_history': '',
            'current_response': '',
            'current_speaker': '',
            'count': 0,
            'judge_decision': ''
        }
    
    debate_state = state['investment_debate_state']
    
    # Get the bear's previous argument (if any) to respond to
    bear_history = debate_state.get('bear_history', '')
    
    # Query memory for similar past situations (only on first round)
    memory_context = ""
    run_config = state.get("run_config", {})
    if debate_state['count'] == 0 and run_config.get("memory_on", False):
        try:
            memory = get_memory()
            
            # Build comprehensive situation description matching storage format
            # Use same structure as stored documents for better semantic matching
            situation_desc = f"""
[TICKER] {ticker}

[FUNDAMENTAL ANALYSIS]
{reports.get('fundamental_analyst', 'N/A')[:800]}

[TECHNICAL ANALYSIS]
{reports.get('technical_analyst', 'N/A')[:800]}

[NEWS]
{reports.get('news_harvester', 'N/A')[:500]}
"""
            
            # Get similar past analyses
            similar = memory.get_similar_past_analyses(
                current_situation=situation_desc,
                ticker=ticker,  # Filter by same ticker for more relevant matches
                n_results=3,  # Increased to get more context
                min_similarity=0.15  # Lowered to account for ChromaDB's conservative similarity scores
            )
            
            if similar:
                memory_context = "\n\n--- LESSONS FROM PAST ANALYSES ---\n"
                for i, mem in enumerate(similar, 1):
                    outcome = mem['metadata'].get('outcome', 'PENDING')
                    pnl = mem['metadata'].get('profit_loss_pct', 'N/A')
                    lesson = mem['metadata'].get('lessons_learned', 'N/A')
                    
                    memory_context += f"""
Past Analysis {i} (Similarity: {mem['similarity']:.0%}):
- Ticker: {mem['metadata']['ticker']}
- Action: {mem['metadata']['action']}
- Outcome: {outcome} (P/L: {pnl}%)
- Lesson Learned: {lesson}
"""
                print(f"[MEMORY] Bull Researcher found {len(similar)} similar past analyses")
        except Exception as e:
            print(f"[MEMORY] Warning: Could not query memory: {str(e)}")
            memory_context = ""
    
    # Horizon context for debate agents
    horizon = state.get('horizon') or state.get('run_config', {}).get('horizon', 'short')
    horizon_days = state.get('horizon_days') or state.get('run_config', {}).get('horizon_days', 10)
    horizon_context = f"TRADING HORIZON: {horizon_days} trading days ({horizon}-term). Tailor your extraction to evidence most likely to materialise within this window."

    single_extraction_mode = _is_single_extraction_mode(state)

    # 1. Construct the prompt for the LLM
    if debate_state['count'] == 0:
        # First round - opening argument with cross-examination prep
        if single_extraction_mode:
            prompt = f"""Role: Upside Catalyst Analyst for {ticker}.
Task: assess the strength of the upside case in the analyst reports for the next {horizon_days} trading days.

{horizon_context}

Use only the reports below. No external facts.
Rate whether the upside evidence is genuinely strong or merely present using the FINAL_VIEW and CONFIDENCE fields as your anchor:
- If any report has FINAL_VIEW: BULLISH with CONFIDENCE: HIGH → upside case is at minimum MODERATE, unless a technically dominant contrary signal (e.g. BEARISH HIGH technical with price well below SMA) completely controls near-term price action.
- If any report has FINAL_VIEW: BULLISH with CONFIDENCE: MEDIUM → upside case is at minimum WEAK.
- If upside is speculative, reversal-only (e.g. mean-reversion bounce only), or unsupported by concrete evidence → WEAK or NO_NEW_UPSIDE.
Do NOT manufacture upside. Do NOT reduce a BULLISH HIGH fundamental report to a bounce narrative.

Full Analyst Reports:
{_format_reports_for_judge(state)}

Output format (strict):
- UPSIDE_STRENGTH: STRONG | MODERATE | WEAK | NO_NEW_UPSIDE
- UPSIDE_NOTE: (omit if UPSIDE_STRENGTH is NO_NEW_UPSIDE) up to 60 words. State the single strongest upside catalyst and its near-term transmission path.

Keep it concise. Start directly with the format."""
        else:
            prompt = f"""Role: Bull Researcher for {ticker}.
    Task: present the strongest directional case for the next {horizon_days} trading days.

    {horizon_context}

    Use only the analyst signal summary below {"and memory notes" if memory_context else ""}. Do not add external facts.
    If evidence is missing, write UNKNOWN.

    Mandatory lead structure:
    1) Start with the single strongest near-term catalyst first.
    2) Include at least one concrete value/date if present in context.

    Falsifiability rule:
    - If 2 or more analyst signals are BEARISH with confidence >= 0.65, you must NOT output BUY.

    Analyst Signal Summary:
    {_format_signal_summary_for_debate(state)}
    {memory_context}

    Output format:
    - LEAD_CATALYST: one line (value/date first when available)
    - THESIS: one line
    - BUY_EVIDENCE: up to 3 bullets (fact -> implication)
    - MAIN_RISK: 1 bullet
    - STANCE: BUY|SELL|HOLD

    Keep under 220 words. Start with "Bull Researcher:"."""
    else:
        # Subsequent rounds - cross-examination with direct rebuttal
        if single_extraction_mode:
            prompt = f"""Role: Upside Catalyst Analyst for {ticker}.
Task: re-assess the strength of the upside case in the analyst reports for the next {horizon_days} trading days.

{horizon_context}

Use only the reports already provided. No outside facts.
Use the FINAL_VIEW and CONFIDENCE fields as your anchor:
- FINAL_VIEW: BULLISH with CONFIDENCE: HIGH → at minimum MODERATE unless a technically dominant contrary signal controls near-term price action.
- FINAL_VIEW: BULLISH with CONFIDENCE: MEDIUM → at minimum WEAK.
Do NOT manufacture upside. Do NOT reduce a BULLISH HIGH fundamental to a bounce narrative.

Full Analyst Reports:
{_format_reports_for_judge(state)}

Output format (strict):
- UPSIDE_STRENGTH: STRONG | MODERATE | WEAK | NO_NEW_UPSIDE
- UPSIDE_NOTE: (omit if UPSIDE_STRENGTH is NO_NEW_UPSIDE) up to 60 words. The single strongest upside catalyst and its near-term transmission path.

Keep it concise. Start directly with the format."""
        else:
            prompt = f"""Role: Bull Researcher (round {debate_state['count']+1}) for {ticker}.
    Task: rebut the strongest bearish points with evidence.

    {horizon_context}

    Use only the signal summary below. No outside facts.

    Falsifiability rule:
    - If bearish evidence dominates after rebuttal, output UPDATED_STANCE as SELL or HOLD (not BUY).

    Signal Summary:
    {_format_signal_summary_for_debate(state)}

    Bear Arguments:
    {bear_history}

    Output format:
    - REBUTTALS: 2 bullets (bear claim -> counter evidence)
    - NEW_BUY_EVIDENCE: up to 2 bullets
    - UPDATED_STANCE: BUY|SELL|HOLD

    Keep under 180 words. Start with "Bull Researcher:"."""
    
    # 2. Call the LLM to generate the argument
    bullish_response = call_llm(prompt)
    
    # 3. Update the debate state
    debate_state['bull_history'] += f"\n\n{bullish_response}"
    debate_state['history'] += f"\n\n{bullish_response}"
    debate_state['current_response'] = bullish_response
    debate_state['current_speaker'] = "Upside Catalyst Analyst" if single_extraction_mode else "Bull Researcher"
    debate_state['count'] += 1
    
    state['investment_debate_state'] = debate_state
    
    # Also update the arguments dict for backward compatibility
    if 'arguments' not in state:
        state['arguments'] = {}
    state['arguments']['bullish'] = debate_state['bull_history']
    
    return state


def bear_researcher_agent(state: dict):
    """
    Reused research-layer node.
    - Stage B / B+: Downside Risk Analyst (non-adversarial extractor)
    - Stage C / D: Bear Researcher in adversarial debate
    """
    reports = state.get('reports', {})
    ticker = state.get('ticker', '')
    debate_state = state.get('investment_debate_state', {})
    
    # Get the bull's previous argument to respond to
    bull_history = debate_state.get('bull_history', '')
    
    # Query memory for past mistakes (only on first response)
    memory_context = ""
    run_config = state.get("run_config", {})
    if debate_state['count'] == 1 and run_config.get("memory_on", False):
        try:
            memory = get_memory()
            
            # Get past mistakes to learn what risks were underestimated
            mistakes = memory.get_past_mistakes(
                ticker=None,
                min_loss_pct=-10.0,
                n_results=2
            )
            
            if mistakes:
                memory_context = "\n\n--- LESSONS FROM PAST MISTAKES ---\n"
                for i, mem in enumerate(mistakes, 1):
                    pnl = mem['metadata'].get('profit_loss_pct', 'N/A')
                    lesson = mem['metadata'].get('lessons_learned', 'N/A')
                    
                    memory_context += f"""
Past Mistake {i}:
- Ticker: {mem['metadata']['ticker']}
- Action: {mem['metadata']['action']}
- Loss: {pnl}%
- What Went Wrong: {lesson}
"""
                print(f"[MEMORY] Bear Researcher found {len(mistakes)} past mistakes to learn from")
        except Exception as e:
            print(f"[MEMORY] Warning: Could not query memory: {str(e)}")
            memory_context = ""
    
    # Horizon context for bear debate
    horizon = state.get('horizon') or state.get('run_config', {}).get('horizon', 'short')
    horizon_days = state.get('horizon_days') or state.get('run_config', {}).get('horizon_days', 10)
    horizon_context = f"TRADING HORIZON: {horizon_days} trading days ({horizon}-term). Tailor your extraction to risks most likely to materialise within this window."

    single_extraction_mode = _is_single_extraction_mode(state)

    # 1. Construct the prompt for the LLM
    if debate_state['count'] == 1:
        # Opening statement - parallel to Bull.
        # Bear argues independently from the full analyst reports; does NOT see Bull's argument.
        # Both sides open without reading each other. Manager judges two independent cases.
        # In round 2+ each side sees the other's full history and can rebut directly.
        if single_extraction_mode:
            prompt = f"""Role: Downside Risk Analyst for {ticker}.
Task: assess whether any downside risk in the analyst reports is strong enough to override the Research Manager's current direction within the next {horizon_days} trading days.

{horizon_context}

Use only the reports below. No external facts.
Your job is NOT to find any downside — it is to rate whether a concrete, specific, near-term risk exists that could cause the current directional thesis to fail.
Ignore generic caution, valuation language, soft chart fragility, or risks that are already acknowledged in the analyst reports and priced in.
If no such risk exists, output OVERRIDE_STRENGTH: NO_OVERRIDE. This is a valid and often correct output.
Do NOT manufacture risk. Do NOT output REDUCE_CONFIDENCE or OVERRIDE unless you can cite a specific piece of evidence.

Full Analyst Reports:
{_format_reports_for_judge(state)}

Output format (strict):
- OVERRIDE_STRENGTH: OVERRIDE | REDUCE_CONFIDENCE | NO_OVERRIDE
- OVERRIDE_NOTE: (required if OVERRIDE_STRENGTH is not NO_OVERRIDE) up to 60 words. State the specific risk, its near-term transmission path, and why it is NOT already priced in.

Keep it concise. Start directly with the format."""
        else:
            prompt = f"""Role: Bear Researcher for {ticker}.
    Task: present the strongest directional case for the next {horizon_days} trading days.

    {horizon_context}

    Use only the analyst signal summary below {"and memory notes" if memory_context else ""}. Do not add external facts.
    If evidence is missing, write UNKNOWN.

    Falsifiability rule:
    - If 2 or more analyst signals are BULLISH with confidence >= 0.65, you must NOT output SELL.

    Analyst Signal Summary:
    {_format_signal_summary_for_debate(state)}

    Bull Argument:
    {bull_history}
    {memory_context}

    Output format:
    - THESIS: one line
    - SELL_EVIDENCE: up to 3 bullets (fact -> implication)
    - MAIN_RISK: 1 bullet
    - STANCE: BUY|SELL|HOLD

    Keep under 220 words. Start with "Bear Researcher:"."""
    else:
        # Subsequent rounds - cross-examination with direct counter-rebuttal
        if single_extraction_mode:
            prompt = f"""Role: Downside Risk Analyst for {ticker}.
Task: re-assess whether any downside risk in the analyst reports is strong enough to override the current directional thesis within the next {horizon_days} trading days.

{horizon_context}

Use only the reports already provided. No outside facts.
If no concrete, specific, near-term override-level risk exists, output OVERRIDE_STRENGTH: NO_OVERRIDE.
Do NOT manufacture risk.

Full Analyst Reports:
{_format_reports_for_judge(state)}

Output format (strict):
- OVERRIDE_STRENGTH: OVERRIDE | REDUCE_CONFIDENCE | NO_OVERRIDE
- OVERRIDE_NOTE: (required if OVERRIDE_STRENGTH is not NO_OVERRIDE) up to 60 words. Specific risk, near-term transmission path, why not already priced.

Keep it concise. Start directly with the format."""
        else:
            prompt = f"""Role: Bear Researcher (round {debate_state['count']+1}) for {ticker}.
    Task: rebut the strongest bullish points with evidence.

    {horizon_context}

    Use only the signal summary below. No outside facts.

    Falsifiability rule:
    - If bullish evidence dominates after rebuttal, output UPDATED_STANCE as BUY or HOLD (not SELL).

    Signal Summary:
    {_format_signal_summary_for_debate(state)}

    Bull Arguments:
    {bull_history}

    Output format:
    - REBUTTALS: 2 bullets (bull claim -> counter evidence)
    - NEW_SELL_EVIDENCE: up to 2 bullets
    - UPDATED_STANCE: BUY|SELL|HOLD

    Keep under 180 words. Start with "Bear Researcher:"."""
    
    # 2. Call the LLM to generate the argument
    bearish_response = call_llm(prompt)
    
    # 3. Update the debate state
    debate_state['bear_history'] += f"\n\n{bearish_response}"
    debate_state['history'] += f"\n\n{bearish_response}"
    debate_state['current_response'] = bearish_response
    debate_state['current_speaker'] = "Downside Risk Analyst (Override Assessor)" if single_extraction_mode else "Bear Researcher"
    debate_state['count'] += 1
    
    state['investment_debate_state'] = debate_state
    
    # Also update the arguments dict for backward compatibility
    state['arguments']['bearish'] = debate_state['bear_history']
    
    return state


def research_manager_agent(state: dict):
    """
    The Research Manager Agent - Judges the debate and makes final investment recommendation.
    """
    debate_state = state.get('investment_debate_state') or {}
    debate_history = (debate_state.get('history', '') or '').strip()
    ticker = state.get('ticker', 'Unknown')
    
    # Horizon for the judge
    horizon = state.get('horizon') or state.get('run_config', {}).get('horizon', 'short')
    horizon_days = state.get('horizon_days') or state.get('run_config', {}).get('horizon_days', 10)

    run_config = state.get("run_config", {}) or {}
    stage = (run_config.get("stage") or "").strip().upper() or None
    debate_mode = (run_config.get("debate_mode") or "on").strip().lower()
    debate_rounds = int(run_config.get("debate_rounds") or 0)
    debate_enabled = debate_mode != "off" and debate_rounds > 0
    single_extraction_mode = _is_single_extraction_mode(state)

    # =========================================================================
    # PATH A: Stage A — clean single-pass LLM synthesis, no rules, no overrides
    # =========================================================================
    if not (debate_enabled and debate_history):
        prompt = f"""Role: Research Manager for {ticker}.
Task: synthesise the three analyst reports below and decide BUY, SELL, or HOLD
      for the next {horizon_days} trading days.

Read the full analyst reports. The signal summary is provided for quick reference,
but your reasoning must be grounded in the prose evidence, not just the labels.

Use HOLD only when you cannot determine which direction has materially stronger
evidence after reading the full reports. If one direction is supported by stronger
evidence — even if not unanimous — prefer that direction over HOLD.
Do not use HOLD as a safe default when evidence is mixed but one side is stronger.

Apply the same standard of evidence to BUY and SELL. Do not privilege either direction.

Signal Summary (quick reference):
{_format_signal_summary_for_debate(state)}

Full Analyst Reports:
{_format_reports_for_judge(state)}

Return JSON:
{{
  "recommendation": "BUY" | "SELL" | "HOLD",
  "confidence_score": <0.0 – 1.0>,
  "primary_drivers": ["<up to 3 key evidence items>"],
  "main_risk": "<single most important counterpoint>"
}}"""

        try:
            decision = call_llm_structured(prompt, StageAManagerDecision, temperature=0.2)
        except Exception as e:
            decision = StageAManagerDecision(
                recommendation="HOLD",
                confidence_score=0.35,
                primary_drivers=["Structured output failed; fallback used"],
                main_risk=f"Parse failure: {e}",
            )

        # LLM recommendation IS the recommendation — no post-override.
        confidence_band = _band_from_score(decision.confidence_score)
        structured_payload = decision.model_dump()
        structured_payload["confidence"] = confidence_band

    # =========================================================================
    # PATH B: Debate-enabled stages (B / B+ / C / D).
    # For B/B+, the extra agent layer is structured evidence extraction, not winner-picking debate.
    # No spread rule for B/B+. Scores are descriptive metadata only and recommendation stays holistic.
    # Spread rule retained for C/D only (separate scoring protocol).
    # =========================================================================
    else:
        upside_note = (debate_state.get('bull_history', '') or '').strip()
        downside_note = (debate_state.get('bear_history', '') or '').strip()
        if single_extraction_mode:
            # --- v6 anchored prior ---
            # Compute Stage A-equivalent prior from analyst reports alone, before reading
            # specialist notes.  This prevents simultaneous contamination: the manager
            # starts from a committed direction and changes it only when the override bar is met.
            prior = _get_stage_a_prior(state, ticker, horizon_days)
            prior_view = prior.recommendation
            # Store in state so downstream stages (B+, C) can read provenance without re-computing.
            state["prior_view"] = prior_view
            prompt = _build_stage_b_manager_prompt(
                state=state,
                ticker=ticker,
                horizon_days=horizon_days,
                upside_note=upside_note,
                downside_note=downside_note,
                prior_view=prior_view,
            )
        else:
            # C/D: spread rule applied — both in prompt and in code post-LLM
            spread_threshold = 1.0
            prompt = _build_stage_cd_manager_prompt(
                state=state,
                ticker=ticker,
                horizon_days=horizon_days,
                spread_threshold=spread_threshold,
                debate_history=debate_history,
            )

        try:
            decision = call_llm_structured(prompt, ResearchManagerDecision, temperature=0.2)
        except Exception as e:
            fallback_text = call_llm(prompt)
            decision = ResearchManagerDecision(
                buy_score=5,
                sell_score=5,
                recommendation="HOLD",
                confidence_score=0.35,
                primary_drivers=["Structured output failed; fallback used"],
                main_risk=f"Parse failure: {e}",
                execution_notes=[fallback_text[:300]],
            )

        # For B/B+: LLM recommendation IS the recommendation — no numeric post-override.
        # buy_score and sell_score are descriptive metadata for UI gauges and calibration.
        # For C/D: spread rule still applies (kept below for those stages).
        if not single_extraction_mode:
            spread = decision.buy_score - decision.sell_score
            if spread >= spread_threshold:
                decision.recommendation = "BUY"
            elif spread <= -spread_threshold:
                decision.recommendation = "SELL"
            else:
                decision.recommendation = "HOLD"

        # LLM-estimated confidence is diagnostic data — no cap applied.
        decision.confidence_score = float(decision.confidence_score or 0.0)

        confidence_band = _band_from_score(decision.confidence_score)
        structured_payload = decision.model_dump()
        structured_payload["confidence"] = confidence_band

    # =========================================================================
    # Common state update
    # =========================================================================
    manager_decision_json = json.dumps(structured_payload, indent=2)
    debate_state['judge_decision'] = manager_decision_json
    state['investment_debate_state'] = debate_state
    state['investment_plan'] = manager_decision_json
    state['investment_plan_structured'] = structured_payload
    state['research_manager_recommendation'] = structured_payload.get("recommendation", "HOLD")

    return state
