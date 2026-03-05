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
    """
    buy_score: float = Field(default=5.0, ge=0, le=10)
    sell_score: float = Field(default=5.0, ge=0, le=10)
    recommendation: Literal["BUY", "SELL", "HOLD"] = "HOLD"
    confidence_score: float = Field(default=0.5, ge=0, le=1)
    primary_drivers: list[str] = Field(default_factory=list)
    main_risk: str = "Unknown"
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


def bull_researcher_agent(state: dict):
    """
    The Bull Researcher Agent - Builds bullish arguments in a debate format.
    Now enhanced with memory to learn from past analyses.
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
    horizon_context = f"TRADING HORIZON: {horizon_days} trading days ({horizon}-term). Tailor your argument to evidence most likely to materialise within this window."

    stage = ((state.get("run_config", {}) or {}).get("stage") or "").strip().upper()

    # 1. Construct the prompt for the LLM
    if debate_state['count'] == 0:
        # First round - opening argument with cross-examination prep
        if stage in {"B", "B+"}:
            prompt = f"""Role: Bull Researcher for {ticker}.
Task: make the strongest BUY case for the next {horizon_days} trading days.

{horizon_context}

Use only the signal summary below {"and memory notes" if memory_context else ""}. No external facts.


Analyst Signal Summary:
{_format_signal_summary_for_debate(state)}
{memory_context}

Output format (strict):
- THESIS: one line
- BUY_EVIDENCE: up to 3 bullets (fact -> implication)
- FAILURE_CONDITION: one line (what would invalidate BUY)
- STANCE: BUY|SELL|HOLD

Keep under 180 words. Start with "Bull Researcher:"."""
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
        if stage in {"B", "B+"}:
            prompt = f"""Role: Bull Researcher (round {debate_state['count']+1}) for {ticker}.
Task: rebut the bear's best claims using evidence from the signal summary.

{horizon_context}

Use only the signal summary. No outside facts.

Signal Summary:
{_format_signal_summary_for_debate(state)}

Bear Arguments:
{bear_history}

Output format (strict):
- REBUTTALS: 2 bullets (bear claim -> bull counter)
- UPDATED_STANCE: BUY|SELL|HOLD

Keep under 140 words. Start with "Bull Researcher:"."""
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
    debate_state['current_speaker'] = "Bull Researcher"
    debate_state['count'] += 1
    
    state['investment_debate_state'] = debate_state
    
    # Also update the arguments dict for backward compatibility
    if 'arguments' not in state:
        state['arguments'] = {}
    state['arguments']['bullish'] = debate_state['bull_history']
    
    return state


def bear_researcher_agent(state: dict):
    """
    The Bear Researcher Agent - Builds bearish arguments in a debate format.
    Now enhanced with memory to learn from past mistakes.
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
    horizon_context = f"TRADING HORIZON: {horizon_days} trading days ({horizon}-term). Tailor your argument to risks most likely to materialise within this window."

    stage = ((state.get("run_config", {}) or {}).get("stage") or "").strip().upper()

    # 1. Construct the prompt for the LLM
    if debate_state['count'] == 1:
        # Opening statement - parallel to Bull.
        # Bear argues independently from signal summary only; does NOT see Bull's argument.
        # Both sides open without reading each other. Manager judges two independent cases.
        # In round 2+ each side sees the other's full history and can rebut directly.
        if stage in {"B", "B+"}:
            prompt = f"""Role: Bear Researcher for {ticker}.
Task: make the strongest independent SELL case for the next {horizon_days} trading days.

{horizon_context}

Use only the signal summary below {"and memory notes" if memory_context else ""}. No external facts.
Build your case independently from the evidence — do not react to any other argument.

Analyst Signal Summary:
{_format_signal_summary_for_debate(state)}
{memory_context}

Output format (strict):
- THESIS: one line
- SELL_EVIDENCE: up to 3 bullets (fact -> implication)
- FAILURE_CONDITION: one line (what would invalidate SELL)
- STANCE: BUY|SELL|HOLD

Keep under 180 words. Start with "Bear Researcher:"."""
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
        if stage in {"B", "B+"}:
            prompt = f"""Role: Bear Researcher (round {debate_state['count']+1}) for {ticker}.
Task: rebut the bull's best claims using evidence from the signal summary.

{horizon_context}

Use only the signal summary. No outside facts.

Signal Summary:
{_format_signal_summary_for_debate(state)}

Bull Arguments:
{bull_history}

Output format (strict):
- REBUTTALS: 2 bullets (bull claim -> bear counter)
- UPDATED_STANCE: BUY|SELL|HOLD

Keep under 140 words. Start with "Bear Researcher:"."""
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
    debate_state['current_speaker'] = "Bear Researcher"
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
    # PATH B: Debate stages (B / B+ / C / D) — LLM judges debate quality directly
    # No spread rule for B/B+. Scores are descriptive metadata only.
    # The recommendation is the LLM's holistic judgment of which argument was stronger.
    # Spread rule retained for C/D only (separate scoring protocol).
    # =========================================================================
    else:
        if stage in {"B", "B+"}:
            prompt = f"""Role: Research Manager / Judge for {ticker}.
Task: decide BUY, SELL, or HOLD for the next {horizon_days} trading days.

You have heard two independent advocates and have the full analyst reports.
Judge which side built the stronger case from the actual evidence in the reports.
If a debater cited something not present in the analyst reports, discount that claim.

Apply the same standard of scrutiny to both sides.
Use HOLD only when the two cases are so evenly matched you cannot determine a winner.
If one side is better supported by the evidence — even if not overwhelmingly — choose that direction.

Analyst Reports:
{_format_reports_for_judge(state)}

Signal Summary:
{_format_signal_summary_for_debate(state)}

Debate:
{debate_history}

Return JSON:
{{
  "recommendation": "BUY" | "SELL" | "HOLD",
  "confidence_score": <0.0 - 1.0>,
  "buy_score": <0-10, how strong the BUY argument was — descriptive only>,
  "sell_score": <0-10, how strong the SELL argument was — descriptive only>,
  "primary_drivers": ["<up to 3 evidence items that decided the judgment>"],
  "main_risk": "<single most important counterpoint to your decision>"
}}"""
        else:
            # C/D: spread rule applied — both in prompt and in code post-LLM
            spread_threshold = 1.0
            prompt = f"""Role: Research Manager.
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
        if stage not in {"B", "B+"}:
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
