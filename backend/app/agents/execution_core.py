# In nexustrader/backend/app/agents/execution_core.py

"""
Execution Core — Trader Agent

Architecture:
- Stages A / B / B+: policy core. Trader echoes the Research Manager and formats
    the rationale without an additional LLM call.
- Stages C / D: independent Trader LLM call is enabled so the downstream risk
    layer can consume Manager-vs-Trader disagreement as genuine signal.

Removed Agents (Redundant):
- Arbitrage Trader: Required complex options data not available
- Value Trader: Duplicated Fundamental Analyst's work (95% overlap)
- Bull Trader: Duplicated Bull Researcher's perspective (90% overlap)
"""

import re
import json

from ..llm import invoke_llm as call_llm
from ..llm import invoke_llm_structured as call_llm_structured
from typing import Optional, Literal
from pydantic import BaseModel, Field, ValidationError
from ..tools.portfolio_tools import calculate_ticker_risk_metrics

class TradingStrategy(BaseModel):
    action: Literal["BUY", "SELL", "HOLD"]
    confidence_score: float = Field(default=0.5, ge=0, le=1)
    entry_price: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    position_size_pct: Optional[float] = Field(default=0, ge=0, le=100)
    rationale: str


def _extract_confidence_band(rationale: str) -> str:
    text = (rationale or "").upper()
    m = re.search(r"CONFIDENCE\s*=\s*(HIGH|MEDIUM|LOW)", text)
    if m:
        return m.group(1)
    m2 = re.search(r"\b(HIGH|MEDIUM|LOW)\b", text)
    return m2.group(1) if m2 else "UNKNOWN"


def _band_from_score(score: float) -> str:
    if score >= 0.75:
        return "HIGH"
    if score >= 0.45:
        return "MEDIUM"
    return "LOW"


def _direction_from_signals(state: dict) -> Optional[str]:
    signals = state.get("signals", {}) or {}
    bull = 0
    bear = 0
    for k in ("fundamental", "technical", "news"):
        d = ((signals.get(k, {}) or {}).get("direction") or "").upper()
        if d == "BULLISH":
            bull += 1
        elif d == "BEARISH":
            bear += 1
    if bull > bear:
        return "BUY"
    if bear > bull:
        return "SELL"
    return None


def _parse_manager_plan(investment_plan: str) -> tuple[Optional[str], float, list[str], str]:
    manager_action = None
    manager_conf = 0.55
    primary_drivers: list[str] = []
    main_risk = ""

    if isinstance(investment_plan, str) and investment_plan.strip():
        try:
            parsed_plan = json.loads(investment_plan)
            rec = (parsed_plan.get("recommendation") or "").upper()
            if rec in {"BUY", "SELL", "HOLD"}:
                manager_action = rec
            try:
                manager_conf = float(parsed_plan.get("confidence_score") or manager_conf)
            except Exception:
                pass
            primary_drivers = [str(x) for x in (parsed_plan.get("primary_drivers") or []) if str(x).strip()]
            main_risk = str(parsed_plan.get("main_risk") or "").strip()
        except Exception:
            plan_upper = investment_plan.upper()
            if "RECOMMENDATION" in plan_upper and "BUY" in plan_upper:
                manager_action = "BUY"
            elif "RECOMMENDATION" in plan_upper and "SELL" in plan_upper:
                manager_action = "SELL"
            elif "RECOMMENDATION" in plan_upper and "HOLD" in plan_upper:
                manager_action = "HOLD"

    manager_conf = max(0.0, min(manager_conf, 1.0))
    # No HOLD confidence clamping — LLM-estimated confidence is diagnostic data.
    # Clamping it to 0.55 would silently corrupt that data for HOLD calls.

    return manager_action, manager_conf, primary_drivers, main_risk


def _stage_a_concise_rationale(
    manager_action: str,
    signals: dict,
    primary_drivers: list[str],
    main_risk: str,
    confidence_band: str,
) -> str:
    action = (manager_action or "HOLD").upper()
    target = "BULLISH" if action == "BUY" else "BEARISH"
    oppose = "BEARISH" if action == "BUY" else "BULLISH"

    signal_items = []
    for key in ("fundamental", "technical", "news"):
        sig = (signals.get(key) or {})
        if not sig:
            continue
        signal_items.append({
            "domain": key,
            "direction": str(sig.get("direction") or "NEUTRAL").upper(),
            "confidence": float(sig.get("confidence") or 0.0),
            "catalyst": str(sig.get("key_catalyst") or "UNKNOWN").strip(),
            "risk": str(sig.get("primary_risk") or "UNKNOWN").strip(),
        })

    pro = None
    con = None
    for item in sorted(signal_items, key=lambda x: x["confidence"], reverse=True):
        if pro is None and item["direction"] == target:
            pro = item
        if con is None and item["direction"] == oppose:
            con = item

    if action == "HOLD":
        for_item = primary_drivers[0] if primary_drivers else "Mixed directional evidence across analyst domains."
        against_item = main_risk or (primary_drivers[1] if len(primary_drivers) > 1 else "No single direction shows durable edge.")
    else:
        for_item = (
            pro["catalyst"] if pro else (primary_drivers[0] if primary_drivers else "Directional evidence supports this action.")
        )
        against_item = (
            con["risk"] if con else (main_risk or (primary_drivers[1] if len(primary_drivers) > 1 else "Counter-evidence remains manageable."))
        )

    return (
        f"FOR: {for_item} "
        f"AGAINST: {against_item} "
        f"DECISION: Executing Research Manager policy-core recommendation to {action}. "
        f"CONFIDENCE={confidence_band}."
    )


def _extract_json_from_text(text: str) -> str:
    """Extract the first JSON object from a model response."""
    cleaned = text.strip()
    # Remove common code fence wrappers
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")
    return cleaned[start:end + 1]


def extract_signal(text: str, ticker: str = "Unknown") -> str:
    """
    LLM-based signal extractor that replaces fragile keyword matching.
    
    When JSON parsing fails or output is ambiguous, this function uses an LLM
    to extract the trading signal (BUY/SELL/HOLD) from natural language text.
    
    This is more robust than regex patterns and can handle:
    - Conversational responses ("I recommend buying...")
    - Embedded signals in long explanations
    - Ambiguous phrasing ("accumulate positions" → BUY)
    - Multi-paragraph responses
    
    Args:
        text: The raw text response from an agent
        ticker: The ticker symbol (for context)
    
    Returns:
        One of: "BUY", "SELL", or "HOLD"
    """
    prompt = f"""Extract the trading signal from this analysis for {ticker}.

ANALYSIS TEXT:
{text}

INSTRUCTIONS:
- Return ONLY one word: BUY, SELL, or HOLD
- Look for explicit recommendations ("I recommend...", "Action: ...", "Decision: ...")
- Interpret synonyms:
  - BUY signals: "buy", "long", "accumulate", "add", "bullish", "go long"
  - SELL signals: "sell", "short", "exit", "reduce", "bearish", "go short"
  - HOLD signals: "hold", "wait", "neutral", "no action", "uncertain"
- If multiple signals exist, prioritize the FINAL recommendation
- If truly ambiguous, default to HOLD

Return ONLY: BUY, SELL, or HOLD (no punctuation, no explanation)"""
    
    try:
        # Use minimal thinking — this is a trivial extraction task
        signal = call_llm(prompt).strip().upper()
        # Validate the response
        if signal in ["BUY", "SELL", "HOLD"]:
            return signal
        # Fallback: check if response contains one of the keywords
        if "BUY" in signal:
            return "BUY"
        elif "SELL" in signal:
            return "SELL"
        else:
            return "HOLD"
    except Exception:
        # If LLM extraction itself fails, default to HOLD
        return "HOLD"


def trading_strategy_synthesizer_agent(state: dict):
    """
    The Trader Agent (formerly "Strategy Synthesizer").

        Architecture:
        - Stages A / B / B+: policy core executor, no independent LLM call.
        - Stages C / D: independent Trader decision-maker so the risk layer can
            adjudicate Manager-vs-Trader tension.
    """
    # Get the investment plan from research manager
    investment_plan = state.get('investment_plan', '')
    ticker = state.get('ticker', 'Unknown')
    horizon = state.get('horizon', 'short')
    horizon_days = state.get('horizon_days', 10)
    decision_style = (state.get("run_config", {}) or {}).get("decision_style", "classification")
    run_config = state.get("run_config", {}) or {}
    stage = (run_config.get("stage") or "").strip().upper() or None
    
    # Fetch real-time price context
    try:
        simulated_date = state.get("simulated_date") or state.get("run_config", {}).get("simulated_date")
        risk_metrics = calculate_ticker_risk_metrics(ticker, as_of=simulated_date)
        current_price_str = risk_metrics.get("current_price", "Unknown")
    except Exception:
        current_price_str = "Unknown"
    
    # Fallback to direct arguments if investment_plan not available
    if not investment_plan:
        arguments = state.get('arguments', {})
        bullish = arguments.get('bullish', '')
        bearish = arguments.get('bearish', '')
        context = f"Bullish Argument:\n{bullish}\n\nBearish Argument:\n{bearish}"
    else:
        context = f"Research Manager's Investment Plan:\n{investment_plan}"

    manager_action, manager_confidence, manager_drivers, manager_main_risk = _parse_manager_plan(investment_plan)
    
    # Build structured signal summary for Stage A (gives Trader concrete evidence to cite)
    signals = state.get("signals", {}) or {}
    signal_lines = []
    for key, label in [("fundamental", "Fundamental"), ("technical", "Technical"), ("news", "News")]:
        s = signals.get(key)
        if s:
            signal_lines.append(
                f"  {label}: direction={s.get('direction','N/A')} | conf={s.get('confidence',0.5):.2f}"
                f" | catalyst={s.get('key_catalyst','UNKNOWN')} | risk={s.get('primary_risk','UNKNOWN')}"
            )
        else:
            signal_lines.append(f"  {label}: No signal available")
    signal_block = "\n".join(signal_lines)

    # Policy core for Stages A / B / B+:
    # Trader echoes the Research Manager — no independent LLM call.
    # Trader independence (full LLM call) only activates at Stage C, where the Risk Debate
    # can consume the Manager-vs-Trader tension as a concrete signal during risk adjudication.
    if stage in {"A", "B", "B+"} and manager_action in {"BUY", "SELL", "HOLD"}:
        trader_action = manager_action
        confidence_band = _band_from_score(manager_confidence)
        strategy = {
            "action": trader_action,
            "confidence_score": manager_confidence,
            "entry_price": None,
            "take_profit": None,
            "stop_loss": None,
            "position_size_pct": 0,
            "rationale": _stage_a_concise_rationale(
                manager_action=manager_action,
                signals=signals,
                primary_drivers=manager_drivers,
                main_risk=manager_main_risk,
                confidence_band=confidence_band,
            ),
        }

        state['trading_strategy'] = strategy
        state['research_manager_recommendation'] = manager_action
        state['trader_recommendation'] = trader_action

        if 'run_metadata' not in state:
            state['run_metadata'] = {}
        state['run_metadata'].update({
            "strategy_action": trader_action,
            "strategy_json_parse_failed": False,
            "strategy_confidence_band": confidence_band,
            "strategy_abstention_overridden": False,
            "research_manager_action": manager_action,
            "trader_disagreed_with_manager": False,
            "policy_core": True,  # Trader = policy executor; no independent LLM call
        })

        return state

    prompt = f"""Role: Trader for {ticker}.
Task: predict direction over the next {horizon_days} trading days.

Current Price: {current_price_str}
Context:
{context}

Rules:
1) Use only context above; no external facts.
2) Prefer directional action (BUY/SELL). Use HOLD only when evidence is genuinely mixed.
3) Output confidence_score in [0, 1] for the chosen action.
4) For classification style, de-emphasize trade sizing details.

Return ONLY valid JSON:
{{
    "action": "BUY|SELL|HOLD",
    "confidence_score": <number 0..1>,
    "entry_price": <number|null>,
    "take_profit": <number|null>,
    "stop_loss": <number|null>,
    "position_size_pct": <number>,
    "rationale": "<2-4 sentences with top evidence>"
}}
"""
    
    # 2. Call the LLM to generate structured strategy
    parse_failed = False
    try:
        strategy_model = call_llm_structured(
            prompt,
            TradingStrategy,
            temperature=0.2,
        )
        strategy = strategy_model.model_dump()
    except (ValueError, ValidationError) as exc:
        parse_failed = True
        # Structured path failed - fallback to text extraction
        try:
            strategy_response = call_llm(prompt)
            extracted_action = extract_signal(strategy_response, ticker)
            strategy = {
                "action": extracted_action,
                "confidence_score": 0.55 if extracted_action != "HOLD" else 0.35,
                "entry_price": None,
                "take_profit": None,
                "stop_loss": None,
                "position_size_pct": 0,
                "rationale": f"Extracted from prose after structured parse failure: {exc}. Original response: {strategy_response[:200]}...",
            }
        except Exception as extract_exc:
            strategy = {
                "action": "HOLD",
                "confidence_score": 0.2,
                "entry_price": None,
                "take_profit": None,
                "stop_loss": None,
                "position_size_pct": 0,
                "rationale": f"Fallback due to parse error ({exc}) and extraction error ({extract_exc}).",
            }
    
    # NO forced alignment for non-Stage-A paths — Trader remains independent.
    
    # Anti-abstention guard: HOLD is only allowed when confidence is LOW.
    trader_action = (strategy.get("action", "HOLD") or "HOLD").upper()
    confidence_band = _extract_confidence_band(strategy.get("rationale", ""))
    if confidence_band == "UNKNOWN":
        confidence_band = _band_from_score(float(strategy.get("confidence_score", 0.5) or 0.5))
        strategy["rationale"] = (
            f"{strategy.get('rationale', '').strip()} CONFIDENCE={confidence_band}"
        ).strip()

    abstention_overridden = False
    # Anti-abstention guard: HOLD is not allowed when the Trader's own confidence is MEDIUM or HIGH.
    # Fallback priority: (1) Research Manager's direction if explicitly BUY/SELL,
    #                    (2) majority vote across analyst signals.
    if trader_action == "HOLD" and confidence_band in {"HIGH", "MEDIUM"}:
        # Prefer Research Manager direction if explicit, else use majority of analyst signals.
        fallback_direction = None
        if manager_action in {"BUY", "SELL"}:
            fallback_direction = manager_action
        else:
            fallback_direction = _direction_from_signals(state)

        if fallback_direction in {"BUY", "SELL"}:
            trader_action = fallback_direction
            strategy["action"] = trader_action
            abstention_overridden = True
            strategy["rationale"] = (
                f"{strategy.get('rationale', '')} "
                f"[AUTO_GUARD] HOLD overridden to {trader_action} because CONFIDENCE={confidence_band}."
            ).strip()

    disagreed = manager_action and trader_action != manager_action
    if disagreed:
        print(f"[TRADER] Independent decision: Trader chose {trader_action}, Research Manager recommended {manager_action}")
    
    # Normalize HOLD to avoid misleading price fields
    if (strategy.get("action") or "").upper() == "HOLD":
        strategy["entry_price"] = None
        strategy["take_profit"] = None
        strategy["stop_loss"] = None
        strategy["position_size_pct"] = 0
    elif (decision_style or "classification").lower() == "classification":
        # Keep this project as directional classification, not portfolio sizing.
        strategy["entry_price"] = None
        strategy["take_profit"] = None
        strategy["stop_loss"] = None
        strategy["position_size_pct"] = 0
    
    # 5. Update the state
    state['trading_strategy'] = strategy
    
    # Store both recommendations for Risk Manager to see the tension
    state['research_manager_recommendation'] = manager_action or "UNKNOWN"
    state['trader_recommendation'] = trader_action

    # Record run metadata for evaluation/debug
    if 'run_metadata' not in state:
        state['run_metadata'] = {}
    state['run_metadata'].update({
        "strategy_action": trader_action,
        "strategy_json_parse_failed": parse_failed,
        "strategy_confidence_band": confidence_band,
        "strategy_abstention_overridden": abstention_overridden,
        "research_manager_action": manager_action,
        "trader_disagreed_with_manager": disagreed,
    })
    
    return state


# ============================================================================
# REMOVED AGENTS - These were redundant and have been disabled
# See documentation/claude_context/WHY_TRADERS_REDUNDANT.md for explanation
# ============================================================================

# def arbitrage_trader_agent(state: dict):
#     """
#     REMOVED: Arbitrage Trader Agent
#     
#     Reason: Required complex real-time options data not available.
#     Used dummy data which made analysis meaningless.
#     Arbitrage trading is out of scope for stock analysis system.
#     """
#     pass

# def value_trader_agent(state: dict):
#     """
#     REMOVED: Value Trader Agent
#     
#     Reason: 95% overlap with Fundamental Analyst.
#     Both analyzed financial statements, valuation metrics, and competitive position.
#     Fundamental Analyst already provides comprehensive value assessment.
#     """
#     pass

# def bull_trader_agent(state: dict):
#     """
#     REMOVED: Bull Trader Agent
#     
#     Reason: 90% overlap with Bull Researcher.
#     Both made bullish case using growth catalysts, momentum, and sentiment.
#     Created confusion by arguing bull case twice in same analysis.
#     Bull Researcher in debate mechanism already provides this perspective.
#     """
#     pass