# In nexustrader/backend/app/agents/research_team.py

import json
import os
from typing import Literal
from pydantic import BaseModel, Field

from ..llm import invoke_llm as call_llm
from ..llm import invoke_llm_structured as call_llm_structured
from ..utils.memory import get_memory


PRO_MODEL_NAME = os.getenv("GEMINI_PRO_MODEL", "gemini-3-pro-preview")


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
    buy_score / sell_score are descriptive metadata only
    (UI gauges, calibration). The LLM's holistic recommendation field is the decision.

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
    Stage B / B+ / C / D use two non-adversarial specialist extractors instead of a mirrored bull/bear pair.
    Fall back to extraction-first routing for custom runs that do not set an explicit stage.
    """
    run_config = state.get("run_config", {}) or {}
    stage = (run_config.get("stage") or "").strip().upper()
    if stage in {"B", "B+", "C", "D"}:
        return True

    debate_mode = (run_config.get("debate_mode") or "on").strip().lower()
    debate_rounds = int(run_config.get("debate_rounds") or 0)
    return debate_mode != "off" and debate_rounds > 0


def _use_two_part_specialist_format(state: dict) -> bool:
    """
    Prompt-format gate for specialist extractors.
    Keep Stage B / B+ on legacy one-part notes for ablation stability.
    Use two-part (core + falsifier) extraction for Stage C / D.
    """
    run_config = state.get("run_config", {}) or {}
    stage = (run_config.get("stage") or "").strip().upper()
    if stage in {"C", "D"}:
        return True
    if stage in {"B", "B+"}:
        return False

    # Fallback for custom runs: tie two-part format to risk debate mode.
    risk_mode = (run_config.get("risk_mode") or "off").strip().lower()
    return risk_mode == "debate"


def _use_pro_stage_a_manager(state: dict) -> bool:
    run_config = state.get("run_config", {}) or {}
    stage = (run_config.get("stage") or "").strip().upper()
    return stage == "A" and bool(run_config.get("use_pro_stage_a_manager", False))


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


def _get_cached_stage_a_prior(state: dict) -> StageAManagerDecision | None:
    run_config = state.get("run_config", {}) or {}
    if not run_config.get("use_cached_stage_a_prior", False):
        return None

    cache_context = state.get("cache_context", {}) or {}
    cached_prior = cache_context.get("cached_stage_a_prior")
    if not isinstance(cached_prior, dict):
        return None

    try:
        return StageAManagerDecision(**cached_prior)
    except Exception:
        return None


def _build_stage_b_manager_prompt(
    state: dict,
    ticker: str,
    horizon_days: int,
    upside_note: str,
    downside_note: str,
    prior_view: str = "HOLD",
) -> str:
    return f"""Role: Research Manager for {ticker}.
Task: decide final BUY, SELL, or HOLD for the next {horizon_days} trading days by stress-testing PRIOR_VIEW with specialist deltas.

PRIOR VIEW: {prior_view}

Use only the evidence provided below. No external facts.
Treat PRIOR_VIEW as the baseline from full analyst reports. Specialist notes are incremental deltas, not replacement theses.

UPSIDE CATALYST HIGHLIGHTS:
{upside_note}

DOWNSIDE RISK HIGHLIGHTS:
{downside_note}

Decision framework:
- Read specialist notes as incremental evidence only.
- Confirm PRIOR_VIEW unless specialist evidence is both genuinely new and direction-changing.
- Override only when a specialist note identifies a specific near-term catalyst or risk that was not explicit in prior evidence and materially changes expected price path.
- Use HOLD only when, after delta review, BUY and SELL paths are both concrete and similarly plausible.
- Do not treat repeated evidence or generic caution as sufficient override.
- Apply the same burden of proof for BUY and SELL.

Field guidance:
- primary_drivers: 1-2 concrete items that drove decision.
- main_risk: single most important named risk.
- override_reason: empty when confirmed; if overridden, state the new evidence and why prior path is invalidated.
- buy_score and sell_score: descriptive only, not decision rules.

Return strict JSON with all fields populated (use concise text when uncertain; do not leave required fields blank):

{{
    "recommendation": "BUY" | "SELL" | "HOLD",
    "prior_view": "{prior_view}",
    "prior_confirmed": true | false,
    "override_reason": "<if prior_confirmed=false, state exact new evidence that met the two-part override bar. Otherwise empty.>",
    "confidence_score": <0.0 - 1.0>,
    "buy_score": <0-10>,
    "sell_score": <0-10>,
    "primary_drivers": ["<evidence 1>", "<evidence 2>"],
    "main_risk": "<single most important named risk to the final decision>",
    "base_view_from_reports": "{prior_view}",
    "base_view_rationale": "<1 sentence: confirm prior or explain override>",
    "upside_note_impact": "<concise: impact of upside note on final view>",
    "downside_note_impact": "<concise: impact of downside note on final view>",
    "actionability_assessment": "<concise: near-term price action path>",
    "hold_gate_assessment": "<concise: whether uncertainty is irresolvable>"
}}"""


def bull_researcher_agent(state: dict):
    """
    Reused research-layer node.
        - Stage B / B+ / C / D: Upside Catalyst Analyst-style non-adversarial extractor
            when debate mode is active
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
    two_part_format = _use_two_part_specialist_format(state)

    # 1. Construct the prompt for the LLM
    if debate_state['count'] == 0:
        # First round - opening argument with cross-examination prep
        if single_extraction_mode:
            if two_part_format:
                prompt = f"""Role: Upside Catalyst Analyst for {ticker}.
Task: extract the strongest near-term upside catalysts from the analyst reports.

{horizon_context}

Use only the reports below. No external facts.
Your objective is to identify any concrete, actionable evidence that supports a breakout or bullish continuation within {horizon_days} trading days.
Evaluate the evidence holistically. Focus on earnings surprises, technical breakouts, or specific positive news events.
Ignore speculative assumptions and focus only on documented catalysts.

Full Analyst Reports:
{_format_reports_for_judge(state)}

Output format (strict):
- UPSIDE_STRENGTH: STRONG | MODERATE | WEAK | NO_NEW_UPSIDE
- UPSIDE_CORE: if UPSIDE_STRENGTH is not NO_NEW_UPSIDE, up to 55 words describing the single strongest upside catalyst and transmission path. If NO_NEW_UPSIDE, output NONE.
- UPSIDE_FALSIFIER: one concise, observable condition that would invalidate UPSIDE_CORE within {horizon_days} trading days. If NO_NEW_UPSIDE, output NONE.

Keep it concise. Start directly with the format."""
            else:
                prompt = f"""Role: Upside Catalyst Analyst for {ticker}.
Task: extract the strongest near-term upside catalysts from the analyst reports.

{horizon_context}

Use only the reports below. No external facts.
Your objective is to identify any concrete, actionable evidence that supports a breakout or bullish continuation within {horizon_days} trading days.
Evaluate the evidence holistically. Focus on earnings surprises, technical breakouts, or specific positive news events.
Ignore speculative assumptions and focus only on documented catalysts.

Full Analyst Reports:
{_format_reports_for_judge(state)}

Output format (strict):
- UPSIDE_STRENGTH: STRONG | MODERATE | WEAK | NO_NEW_UPSIDE
- UPSIDE_NOTE: (omit if UPSIDE_STRENGTH is NO_NEW_UPSIDE) up to 80 words. State the most powerful upside catalyst found and how it transmits into price action.

Keep it concise. Start directly with the format."""
        else:
            prompt = f"""Role: Bull Researcher for {ticker}.
    Task: advocate for the most compelling bullish interpretation of the evidence, if one exists.

    {horizon_context}

    Use only the analyst signal summary below {"and memory notes" if memory_context else ""}. Do not add external facts.
    If evidence is missing, write UNKNOWN.
    If the evidence points overwhelmingly downward, concede by outputting a HOLD or SELL stance. Do not invent a bullish case from weak evidence.

    Mandatory lead structure:
    1) Start with the single strongest near-term catalyst first.
    2) Include at least one concrete value/date if present in context.

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
            if two_part_format:
                prompt = f"""Role: Upside Catalyst Analyst for {ticker}.
Task: re-assess the strength of the upside case in the analyst reports for the next {horizon_days} trading days.

{horizon_context}

Use only the reports already provided. No outside facts.
Do not force upside from prior labels. Re-assess only from concrete evidence that can plausibly move price within the stated horizon.
If no specific, near-term upside catalyst is present, output UPSIDE_STRENGTH: NO_NEW_UPSIDE.

Full Analyst Reports:
{_format_reports_for_judge(state)}

Output format (strict):
- UPSIDE_STRENGTH: STRONG | MODERATE | WEAK | NO_NEW_UPSIDE
- UPSIDE_CORE: if UPSIDE_STRENGTH is not NO_NEW_UPSIDE, up to 45 words naming the single strongest upside catalyst and transmission path. If NO_NEW_UPSIDE, output NONE.
- UPSIDE_FALSIFIER: one concise, observable condition that would invalidate UPSIDE_CORE within {horizon_days} trading days. If NO_NEW_UPSIDE, output NONE.

Keep it concise. Start directly with the format."""
            else:
                prompt = f"""Role: Upside Catalyst Analyst for {ticker}.
Task: re-assess the strength of the upside case in the analyst reports for the next {horizon_days} trading days.

{horizon_context}

Use only the reports already provided. No outside facts.
Do not force upside from prior labels. Re-assess only from concrete evidence that can plausibly move price within the stated horizon.
If no specific, near-term upside catalyst is present, output UPSIDE_STRENGTH: NO_NEW_UPSIDE.

Full Analyst Reports:
{_format_reports_for_judge(state)}

Output format (strict):
- UPSIDE_STRENGTH: STRONG | MODERATE | WEAK | NO_NEW_UPSIDE
- UPSIDE_NOTE: (omit if UPSIDE_STRENGTH is NO_NEW_UPSIDE) up to 60 words. The single strongest upside catalyst and its near-term transmission path.

Keep it concise. Start directly with the format."""
        else:
            prompt = f"""Role: Bull Researcher (round {debate_state['count']+1}) for {ticker}.
    Task: rebut the strongest bearish points using only concrete evidence.

    {horizon_context}

    Use only the signal summary below. No outside facts.
    Concede points where the bearish evidence is demonstrably stronger. Do not force a BUY stance if the evidence after rebuttal points downwards.

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
        - Stage B / B+ / C / D: Downside Risk Analyst-style non-adversarial extractor
            when debate mode is active
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
    two_part_format = _use_two_part_specialist_format(state)

    # 1. Construct the prompt for the LLM
    if debate_state['count'] == 1:
        # Opening statement - parallel to Bull.
        # Bear argues independently from the full analyst reports; does NOT see Bull's argument.
        # Both sides open without reading each other. Manager judges two independent cases.
        # In round 2+ each side sees the other's full history and can rebut directly.
        if single_extraction_mode:
            if two_part_format:
                prompt = f"""Role: Downside Risk Analyst for {ticker}.
Task: extract the strongest near-term downside risks and bearish catalysts from the analyst reports.

{horizon_context}

Use only the reports below. No external facts.
Your objective is to identify any concrete, actionable evidence that supports a breakdown, reversal, or continued negative momentum within {horizon_days} trading days.
Focus on weakening fundamentals, technical breakdowns, or specific negative catalysts.
Do not highlight generic market caution. Look for active, specific threats to the stock price.

Full Analyst Reports:
{_format_reports_for_judge(state)}

Output format (strict):
- DOWNSIDE_STRENGTH: STRONG | MODERATE | WEAK | NO_NEW_DOWNSIDE
- DOWNSIDE_CORE: if DOWNSIDE_STRENGTH is not NO_NEW_DOWNSIDE, up to 55 words describing the single strongest downside risk and impact mechanism. If NO_NEW_DOWNSIDE, output NONE.
- DOWNSIDE_FALSIFIER: one concise, observable condition that would invalidate DOWNSIDE_CORE within {horizon_days} trading days. If NO_NEW_DOWNSIDE, output NONE.

Keep it concise. Start directly with the format."""
            else:
                prompt = f"""Role: Downside Risk Analyst for {ticker}.
Task: extract the strongest near-term downside risks and bearish catalysts from the analyst reports.

{horizon_context}

Use only the reports below. No external facts.
Your objective is to identify any concrete, actionable evidence that supports a breakdown, reversal, or continued negative momentum within {horizon_days} trading days.
Focus on weakening fundamentals, technical breakdowns, or specific negative catalysts.
Do not highlight generic market caution. Look for active, specific threats to the stock price.

Full Analyst Reports:
{_format_reports_for_judge(state)}

Output format (strict):
- DOWNSIDE_STRENGTH: STRONG | MODERATE | WEAK | NO_NEW_DOWNSIDE
- DOWNSIDE_NOTE: (omit if DOWNSIDE_STRENGTH is NO_NEW_DOWNSIDE) up to 80 words. State the single strongest downside risk found and its exact mechanism of impact.

Keep it concise. Start directly with the format."""
        else:
            prompt = f"""Role: Bear Researcher for {ticker}.
    Task: advocate for the most compelling bearish interpretation of the evidence (downside risks and catalysts), if one exists.

    {horizon_context}

    Use only the analyst signal summary below {"and memory notes" if memory_context else ""}. Do not add external facts.
    If evidence is missing, write UNKNOWN.
    If the evidence points overwhelmingly upward, concede by outputting a HOLD or BUY stance. Do not invent a bearish case from weak evidence.

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
            if two_part_format:
                prompt = f"""Role: Downside Risk Analyst for {ticker}.
Task: re-assess whether any downside risk in the analyst reports serves as a strong bearish catalyst within the next {horizon_days} trading days.

{horizon_context}

Use only the reports already provided. No outside facts.
If no concrete, specific, near-term risk exists, output DOWNSIDE_STRENGTH: NO_NEW_DOWNSIDE.

Full Analyst Reports:
{_format_reports_for_judge(state)}

Output format (strict):
- DOWNSIDE_STRENGTH: STRONG | MODERATE | WEAK | NO_NEW_DOWNSIDE
- DOWNSIDE_CORE: if DOWNSIDE_STRENGTH is not NO_NEW_DOWNSIDE, up to 45 words naming the strongest downside risk and impact mechanism. If NO_NEW_DOWNSIDE, output NONE.
- DOWNSIDE_FALSIFIER: one concise, observable condition that would invalidate DOWNSIDE_CORE within {horizon_days} trading days. If NO_NEW_DOWNSIDE, output NONE.

Keep it concise. Start directly with the format."""
            else:
                prompt = f"""Role: Downside Risk Analyst for {ticker}.
Task: re-assess whether any downside risk in the analyst reports serves as a strong bearish catalyst within the next {horizon_days} trading days.

{horizon_context}

Use only the reports already provided. No outside facts.
If no concrete, specific, near-term risk exists, output DOWNSIDE_STRENGTH: NO_NEW_DOWNSIDE.

Full Analyst Reports:
{_format_reports_for_judge(state)}

Output format (strict):
- DOWNSIDE_STRENGTH: STRONG | MODERATE | WEAK | NO_NEW_DOWNSIDE
- DOWNSIDE_NOTE: (omit if DOWNSIDE_STRENGTH is NO_NEW_DOWNSIDE) up to 80 words.

Keep it concise. Start directly with the format."""
        else:
            prompt = f"""Role: Bear Researcher (round {debate_state['count']+1}) for {ticker}.
    Task: rebut the strongest bullish points using only concrete evidence.

    {horizon_context}

    Use only the signal summary below. No outside facts.
    Concede points where the bullish evidence is demonstrably stronger. Do not force a SELL stance if the evidence after rebuttal points upwards.

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
    debate_mode = (run_config.get("debate_mode") or "on").strip().lower()
    debate_rounds = int(run_config.get("debate_rounds") or 0)
    debate_enabled = debate_mode != "off" and debate_rounds > 0

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
            manager_model = PRO_MODEL_NAME if _use_pro_stage_a_manager(state) else None
            decision = call_llm_structured(
                prompt,
                StageAManagerDecision,
                temperature=0.2,
                model_name=manager_model,
            )
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
    # Shared manager policy across B / B+ / C / D.
    # Research specialists are structured extractors, not winner-picking debate.
    # Scores are descriptive metadata only; recommendation remains holistic.
    # Stage differentiation after this point comes from Trader behavior and risk_mode.
    # =========================================================================
    else:
        upside_note = (debate_state.get('bull_history', '') or '').strip()
        downside_note = (debate_state.get('bear_history', '') or '').strip()
        # --- v6 anchored prior ---
        # Compute Stage A-equivalent prior from analyst reports alone, before reading
        # specialist notes. This prevents simultaneous contamination: the manager
        # starts from a committed direction and changes it only when the override bar is met.
        cached_prior = _get_cached_stage_a_prior(state)
        prior = cached_prior or _get_stage_a_prior(state, ticker, horizon_days)
        prior_view = prior.recommendation
        # Store in state so downstream stages (B+, C, D) can read provenance without re-computing.
        state["prior_view"] = prior_view
        cache_context = state.get("cache_context", {}) or {}
        cache_context["cached_stage_a_prior_used"] = bool(cached_prior is not None)
        state["cache_context"] = cache_context
        provenance = state.get("provenance", {}) or {}
        cache_provenance = provenance.get("cache", {}) or {}
        cache_provenance["cached_stage_a_prior_used"] = bool(cached_prior is not None)
        provenance["cache"] = cache_provenance
        state["provenance"] = provenance
        prompt = _build_stage_b_manager_prompt(
            state=state,
            ticker=ticker,
            horizon_days=horizon_days,
            upside_note=upside_note,
            downside_note=downside_note,
            prior_view=prior_view,
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

        # LLM recommendation IS the recommendation — no numeric post-override.
        # buy_score and sell_score are descriptive metadata for calibration.

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
