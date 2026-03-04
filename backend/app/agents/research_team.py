# In nexustrader/backend/app/agents/research_team.py

import json
from typing import Literal
from pydantic import BaseModel, Field

from ..llm import invoke_llm as call_llm
from ..llm import invoke_llm_structured as call_llm_structured
from ..utils.memory import get_memory


class ResearchManagerDecision(BaseModel):
    # --- Vote+Strength fields: used for Stage A weighted directional scoring ---
    # vote = direction of evidence; strength = how strong/clear the evidence is
    fundamental_vote: Literal["BULLISH", "BEARISH", "NEUTRAL"] = "NEUTRAL"
    fundamental_strength: Literal["STRONG", "MED", "WEAK"] = "MED"
    technical_vote: Literal["BULLISH", "BEARISH", "NEUTRAL"] = "NEUTRAL"
    technical_strength: Literal["STRONG", "MED", "WEAK"] = "MED"
    news_vote: Literal["BULLISH", "BEARISH", "NEUTRAL"] = "NEUTRAL"
    news_strength: Literal["STRONG", "MED", "WEAK"] = "MED"
    # --- Legacy numeric scores: retained for debate-mode stages (B/C/D) ---
    buy_score: float = Field(default=5.0, ge=0, le=10)
    sell_score: float = Field(default=5.0, ge=0, le=10)
    # --- Common fields ---
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
    if debate_state['count'] == 0 and run_config.get("memory_on", True):
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
    horizon_context = f"TRADING HORIZON: {horizon_days} days ({horizon}-term). Tailor ALL arguments to catalysts and risks relevant within this window. For short-term, weight technical momentum and news over long-term valuation."

    # 1. Construct the prompt for the LLM
    if debate_state['count'] == 0:
        # First round - opening argument with cross-examination prep
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
    if debate_state['count'] == 1 and run_config.get("memory_on", True):
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
    horizon_context = f"TRADING HORIZON: {horizon_days} days ({horizon}-term). Tailor ALL arguments to risks that could materialise within this window. For short-term, weight technical breakdowns and near-term news risks over long-term structural concerns."

    # 1. Construct the prompt for the LLM
    if debate_state['count'] == 1:
        # First response - cross-examine bull's opening argument
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

    # Stage A is no-debate by design; widen threshold to reduce score-noise flips.
    spread_threshold = 2.0 if stage == "A" else 1.0

    # 1. Construct the prompt for structured LLM output
    if debate_enabled and debate_history:
        # Debate-enabled stages (B/C/D): score based on debate transcript.
        prompt = f"""Role: Research Manager.
Task: choose BUY, SELL, or HOLD for {ticker} over the next {horizon_days} trading days.

Use only the evidence below. No external facts.
Apply symmetric criteria for BUY and SELL.

Scoring policy (required, apply exactly):
1) Score the BUY case from 0-10 using only concrete evidence in debate.
2) Score the SELL case from 0-10 using only concrete evidence in debate.
3) Decision rule:
   - If BUY_SCORE - SELL_SCORE >= {spread_threshold:g} -> BUY
   - If SELL_SCORE - BUY_SCORE >= {spread_threshold:g} -> SELL
   - Otherwise -> HOLD

Set confidence_score in [0, 1] as probability-like confidence for the chosen direction.

Primary driver rule (required):
- primary_drivers must include BOTH: (a) 1-2 drivers supporting the chosen direction and (b) 1 driver labeled "COUNTERPOINT:".

Signal Summary:
{_format_signal_summary_for_debate(state)}

Analyst Reports:
{_format_reports_for_judge(state)}

Debate:
{debate_history}

Return strict JSON matching schema fields:
buy_score, sell_score, recommendation, confidence_score, primary_drivers, main_risk, execution_notes."""
    else:
        # No-debate mode (Stage A): vote + strength per domain, weighted score decides.
        prompt = f"""Role: Research Manager.
Task: assess BUY, SELL, or HOLD for {ticker} over the next {horizon_days} trading days.

Use only the evidence below. No external facts. Apply symmetric criteria.

Step 1 — For each analyst domain cast a direction vote and a strength rating.
  direction: BULLISH | BEARISH | NEUTRAL
  strength:  STRONG (clear, unambiguous evidence) | MED (moderate, some caveats) | WEAK (thin or conflicted)
  NEUTRAL direction always has strength WEAK — they carry zero weight.

Step 2 — Weighted directional score (Python enforces the final call, so be accurate):
  BULLISH/STRONG = +2, BULLISH/MED = +1, BULLISH/WEAK = +0.5
  BEARISH/STRONG = -2, BEARISH/MED = -1, BEARISH/WEAK = -0.5
  NEUTRAL        =  0  (regardless of strength)

  Decision threshold = 1.5:
    total > +1.5  → BUY
    total < -1.5  → SELL
    otherwise     → HOLD

Step 3 — Recommendation must be consistent with the score above.
Step 4 — primary_drivers: 1–2 drivers supporting the direction + 1 labeled "COUNTERPOINT:".
Step 5 — main_risk: strongest counterpoint.

Confidence calibration:
  HOLD                           → confidence_score ≤ 0.55
  BUY/SELL |score| 1.5–3.0       → 0.55–0.72
  BUY/SELL |score| > 3.0         → 0.72–0.90

Signal Summary:
{_format_signal_summary_for_debate(state)}

Analyst Reports:
{_format_reports_for_judge(state)}

Return strict JSON:
fundamental_vote, fundamental_strength, technical_vote, technical_strength,
news_vote, news_strength, recommendation, confidence_score,
primary_drivers, main_risk, execution_notes."""
    
    # 2. Call the LLM and validate structured decision
    try:
        manager_decision_structured = call_llm_structured(
            prompt,
            ResearchManagerDecision,
            temperature=0.2,
        )
    except Exception as e:
        fallback = call_llm(prompt)
        manager_decision_structured = ResearchManagerDecision(
            buy_score=5,
            sell_score=5,
            recommendation="HOLD",
            confidence_score=0.35,
            primary_drivers=["Structured output failed; fallback used"],
            main_risk=f"Parse/structured failure: {e}",
            execution_notes=[fallback[:300]],
        )

    # Deterministic post-check: enforce decision rule in code (overrides LLM recommendation)
    if not (debate_enabled and debate_history):
        # Stage A / no-debate: weighted vote (direction × strength) determines recommendation
        _STRENGTH_W = {"STRONG": 2.0, "MED": 1.0, "WEAK": 0.5}
        _DIR_SIGN = {"BULLISH": 1, "BEARISH": -1, "NEUTRAL": 0}
        _STAGE_A_THRESHOLD = 1.5

        def _wvote(direction: str, strength: str) -> float:
            d = _DIR_SIGN.get((direction or "NEUTRAL").upper(), 0)
            s = _STRENGTH_W.get((strength or "MED").upper(), 1.0)
            return d * s

        wt_score = sum([
            _wvote(manager_decision_structured.fundamental_vote, manager_decision_structured.fundamental_strength),
            _wvote(manager_decision_structured.technical_vote, manager_decision_structured.technical_strength),
            _wvote(manager_decision_structured.news_vote, manager_decision_structured.news_strength),
        ])

        if wt_score > _STAGE_A_THRESHOLD:
            manager_decision_structured.recommendation = "BUY"
        elif wt_score < -_STAGE_A_THRESHOLD:
            manager_decision_structured.recommendation = "SELL"
        else:
            manager_decision_structured.recommendation = "HOLD"

        # Expose score for downstream confidence calibration
        _wt_score_abs = abs(wt_score)
    else:
        # Debate-mode stages (B/C/D): keep numeric spread rule
        spread = manager_decision_structured.buy_score - manager_decision_structured.sell_score
        if spread >= spread_threshold:
            manager_decision_structured.recommendation = "BUY"
        elif spread <= -spread_threshold:
            manager_decision_structured.recommendation = "SELL"
        else:
            manager_decision_structured.recommendation = "HOLD"

    # Confidence sanity clamp (diagnostics; does not change recommendation).
    try:
        cs = float(manager_decision_structured.confidence_score or 0.0)
    except Exception:
        cs = 0.0
    rec = (manager_decision_structured.recommendation or "HOLD").upper()
    if rec == "HOLD":
        manager_decision_structured.confidence_score = min(cs, 0.55)
    elif not (debate_enabled and debate_history):
        # Stage A: calibrate confidence to weighted-score magnitude
        _wt_abs = locals().get("_wt_score_abs", 1.5)
        if _wt_abs > 3.0:
            manager_decision_structured.confidence_score = min(max(cs, 0.72), 0.90)
        else:
            manager_decision_structured.confidence_score = min(max(cs, 0.55), 0.72)
    else:
        manager_decision_structured.confidence_score = min(cs, 0.90)

    # Add compatibility confidence band for downstream evaluators
    confidence_band = _band_from_score(manager_decision_structured.confidence_score)
    structured_payload = manager_decision_structured.model_dump()
    structured_payload["confidence"] = confidence_band

    manager_decision_json = json.dumps(structured_payload, indent=2)
    
    # 3. Update the state
    debate_state['judge_decision'] = manager_decision_json
    state['investment_debate_state'] = debate_state
    state['investment_plan'] = manager_decision_json
    state['investment_plan_structured'] = structured_payload
    state['research_manager_recommendation'] = manager_decision_structured.recommendation
    
    return state
