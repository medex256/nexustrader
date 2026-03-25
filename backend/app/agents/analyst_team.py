# In nexustrader/backend/app/agents/analyst_team.py

from ..tools.fundamental_data_tools import (
    get_financial_statements,
    get_financial_ratios,
    get_analyst_ratings,
    get_balance_sheet,
    get_cash_flow,
)
from ..tools.technical_analysis_tools import get_historical_price_data, calculate_technical_indicators, plot_stock_chart
from ..tools.news_tools import search_news
from ..llm import invoke_llm as call_llm
from ..utils.shared_context import shared_context
import re
# from ..graph.state import AgentState # We will define this later


def _has_cached_analyst_output(state: dict, report_key: str, signal_key: str) -> bool:
    run_config = state.get("run_config", {}) or {}
    if not run_config.get("use_cached_stage_a_reports", False):
        return False

    reports = state.get("reports", {}) or {}
    signals = state.get("signals", {}) or {}
    return bool(reports.get(report_key)) and signal_key in signals


def _normalize_markdown_for_parse(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\u00a0", " ")
    normalized = re.sub(r"[`*_]+", "", normalized)
    return normalized


def _clean_extracted_line(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" :;.-")


def _linewise_label_value(lines: list[str], labels: list[str]) -> str | None:
    canonical_labels = {re.sub(r"[\s_]+", "", label).upper() for label in labels}

    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        no_prefix = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line)
        match = re.match(r"^(?P<label>[A-Za-z_ ]{3,40})\s*:\s*(?P<value>.*)$", no_prefix)
        if not match:
            continue

        label_key = re.sub(r"[\s_]+", "", match.group("label")).upper()
        if label_key not in canonical_labels:
            continue

        value = _clean_extracted_line(match.group("value"))
        if value:
            return value

        for next_line in lines[idx + 1:]:
            candidate = _clean_extracted_line(next_line)
            if candidate:
                return candidate
    return None


def _first_section_item(lines: list[str], section_labels: list[str]) -> str | None:
    canonical_labels = {re.sub(r"[\s_]+", "", label).upper() for label in section_labels}

    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        no_prefix = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line)
        match = re.match(r"^(?P<label>[A-Za-z_ ]{3,40})\s*:\s*(?P<value>.*)$", no_prefix)
        if not match:
            continue

        label_key = re.sub(r"[\s_]+", "", match.group("label")).upper()
        if label_key not in canonical_labels:
            continue

        inline_value = _clean_extracted_line(match.group("value"))
        if inline_value and inline_value.upper() not in {"NONE IDENTIFIED", "N/A"}:
            return inline_value

        for next_line in lines[idx + 1:]:
            if not next_line.strip():
                continue

            next_no_prefix = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", next_line.strip())
            if re.match(r"^[A-Za-z_ ]{3,40}\s*:", next_no_prefix):
                break

            candidate = _clean_extracted_line(next_line)
            if candidate:
                return candidate
    return None


def _record_signal_parse_provenance(state: dict, analyst_key: str, parse_meta: dict) -> None:
    if "provenance" not in state:
        state["provenance"] = {}
    signal_parse = state["provenance"].setdefault("signal_parse", {})

    signal_parse["total"] = int(signal_parse.get("total", 0)) + 1
    failures_before = int(signal_parse.get("failures", 0))
    failed = not (parse_meta.get("direction_found", False) and parse_meta.get("confidence_found", False))
    if failed:
        signal_parse["failures"] = failures_before + 1
    else:
        signal_parse["failures"] = failures_before

    by_analyst = signal_parse.setdefault("by_analyst", {})
    analyst_stats = by_analyst.setdefault(analyst_key, {"total": 0, "failures": 0})
    analyst_stats["total"] = int(analyst_stats.get("total", 0)) + 1
    if failed:
        analyst_stats["failures"] = int(analyst_stats.get("failures", 0)) + 1


def _extract_analyst_signal(analysis_text: str) -> tuple[dict, dict]:
    """
    Extract a structured directional signal by parsing the labelled output fields
    that analyst prompts already produce (FINAL_VIEW, CONFIDENCE, etc.).

    Replaces the old keyword-frequency counting approach, which was unreliable
    because "not bullish" had the same weight as "strongly bullish".
    Zero extra LLM calls — pure regex on the structured analyst output.
    """
    normalized_text = _normalize_markdown_for_parse(analysis_text)
    lines = [line.rstrip() for line in normalized_text.split("\n")]

    # --- Direction: FINAL_VIEW field (all three analyst prompts output this) ---
    direction = "NEUTRAL"
    _direction_parsed = False
    direction_value = _linewise_label_value(lines, ["FINAL_VIEW"])
    if direction_value and direction_value.upper() in {"BULLISH", "BEARISH", "NEUTRAL"}:
        direction = direction_value.upper()
        _direction_parsed = True
    else:
        tone_value = _linewise_label_value(lines, ["TONE"])
        if tone_value and tone_value.upper() in {"BULLISH", "BEARISH", "NEUTRAL"}:
            direction = tone_value.upper()
            _direction_parsed = True

    # Hard fallback: parse FINAL_VIEW anywhere in normalized text if line-wise parsing missed.
    if not _direction_parsed:
        fallback_match = re.search(r"\bFINAL\s*[_ ]?VIEW\b\s*:\s*(BULLISH|BEARISH|NEUTRAL)", normalized_text, flags=re.IGNORECASE)
        if fallback_match:
            direction = fallback_match.group(1).upper()
            _direction_parsed = True

    # --- Confidence: CONFIDENCE field ---
    confidence_level = "MEDIUM"
    _confidence_parsed = False
    confidence_value = _linewise_label_value(lines, ["CONFIDENCE"])
    if confidence_value and confidence_value.upper() in {"HIGH", "MEDIUM", "LOW"}:
        confidence_level = confidence_value.upper()
        _confidence_parsed = True

    # Log parse misses so we can monitor format-compliance rate
    if not _direction_parsed or not _confidence_parsed:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "[signal_extract] Parse miss — direction_found=%s confidence_found=%s | "
            "text_snippet=%.120s",
            _direction_parsed, _confidence_parsed,
            normalized_text.replace("\n", " "),
        )

    conf_map = {"HIGH": 0.80, "MEDIUM": 0.65, "LOW": 0.50}
    confidence = conf_map.get(confidence_level, 0.65)
    # NEUTRAL views cannot carry HIGH confidence
    if direction == "NEUTRAL":
        confidence = min(confidence, 0.55)

    # --- Magnitude: derived from confidence level (0 for NEUTRAL) ---
    if direction == "NEUTRAL":
        magnitude = 0.0
    else:
        mag_map = {"HIGH": 0.80, "MEDIUM": 0.50, "LOW": 0.25}
        magnitude = mag_map.get(confidence_level, 0.50)

    # --- Key catalyst: first bullet from EVIDENCE or CATALYSTS section ---
    key_catalyst = "No clear catalyst identified"
    catalyst_value = _first_section_item(lines, ["EVIDENCE", "CATALYSTS"])
    if catalyst_value:
        key_catalyst = catalyst_value[:140]

    # --- Primary risk: KEY_UNCERTAINTY or KEY_EVENT_RISK ---
    primary_risk = "No explicit primary risk provided"
    risk_value = _linewise_label_value(lines, ["KEY_UNCERTAINTY", "KEY_EVENT_RISK", "MAIN_RISK"])
    if not risk_value:
        risk_value = _first_section_item(lines, ["RISKS", "RISK"])
    if risk_value:
        primary_risk = _clean_extracted_line(risk_value)[:140]

    signal = {
        "direction": direction,
        "magnitude": magnitude,
        "confidence": confidence,
        "key_factor": f"FINAL_VIEW={direction} CONFIDENCE={confidence_level}",
        "key_catalyst": key_catalyst,
        "primary_risk": primary_risk,
    }
    parse_meta = {
        "direction_found": _direction_parsed,
        "confidence_found": _confidence_parsed,
    }
    return signal, parse_meta


def fundamental_analyst_agent(state: dict):
    """
    The Fundamental Analyst Agent.
    """
    if _has_cached_analyst_output(state, "fundamental_analyst", "fundamental"):
        return state

    ticker = state['ticker']
    simulated_date = state.get('simulated_date')  # Get as_of date for point-in-time data
    horizon = state.get('horizon') or state.get('run_config', {}).get('horizon', 'short')
    horizon_days = state.get('horizon_days') or state.get('run_config', {}).get('horizon_days', 10)

    # Horizon-specific focus instructions
    _FUNDAMENTAL_HORIZON_FOCUS = {
        'short': f'TRADING HORIZON: {horizon_days} days (short-term). Focus on: recent earnings surprise (beat/miss), QoQ revenue acceleration, any guidance revision, near-term catalysts. De-emphasise long-term valuation multiples.',
        'medium': f'TRADING HORIZON: {horizon_days} days (medium-term). Balance: recent earnings trend, forward guidance, sector rotation, valuation vs growth rate.',
        'long': f'TRADING HORIZON: {horizon_days} days (long-term). Focus on: multi-year revenue trajectory, competitive moat, balance-sheet strength, DCF valuation vs peers.',
    }
    horizon_focus = _FUNDAMENTAL_HORIZON_FOCUS.get(horizon, _FUNDAMENTAL_HORIZON_FOCUS['short'])

    # 1. Get the financial data using the tools (with proper date scoping)
    financial_statements = get_financial_statements(ticker, as_of=simulated_date)
    financial_ratios = get_financial_ratios(ticker, as_of=simulated_date)
    analyst_ratings = get_analyst_ratings(ticker, as_of=simulated_date)

    # 2. Construct the prompt for the LLM
    prompt = f"""Fundamental analysis for {ticker}.

Horizon: {horizon_days} trading days.
{horizon_focus}

Your objective is to identify active, near-term fundamental drivers that will likely impact the price within {horizon_days} trading days.
Focus strongly on recent changes: earnings surprises, forward guidance shifts, margin expansion/contraction, and actionable analyst expectation gaps.
Evaluate both upside and downside drivers with equal weight. Treat high-quality but stagnant companies and generic risks as background context.
Rely strictly on the provided financial data. If data is missing, write UNKNOWN.
Formulate an evidence-backed view based on live metrics rather than generalized industry narratives or assumptions about market reactions.
If the evidence is mixed, identify which side has the slight edge. Use NEUTRAL only if the data is perfectly balanced and utterly lacks any near-term catalyst.

Data:
Financial Statements: {financial_statements}
Financial Ratios: {financial_ratios}
Analyst Ratings: {analyst_ratings}

Output exactly:
1) EVIDENCE: 3 concise bullets maximum (what changed now -> why it matters within this horizon)
2) RISKS: 2 concise bullets maximum (active fundamental counterforces, not generic company weaknesses)
3) FINAL_VIEW: BULLISH|BEARISH|NEUTRAL
4) CONFIDENCE: HIGH|MEDIUM|LOW
5) KEY_UNCERTAINTY: one line

Keep under 150 words."""
    
    # 3. Call the LLM to generate the analysis (low temperature: factual data, not creativity)
    analysis_report = call_llm(prompt, temperature=0.3, call_name="Fundamental_Analyst")

    # 4. Extract structured signal (zero extra LLM calls — keyword scoring)
    if 'signals' not in state:
        state['signals'] = {}
    fundamental_signal, parse_meta = _extract_analyst_signal(analysis_report)
    state['signals']['fundamental'] = fundamental_signal
    _record_signal_parse_provenance(state, "fundamental", parse_meta)

    # 5. Update the state
    if 'reports' not in state:
        state['reports'] = {}
    state['reports']['fundamental_analyst'] = analysis_report

    return state

def technical_analyst_agent(state: dict):
    """
    The Technical Analyst Agent.
    """
    if _has_cached_analyst_output(state, "technical_analyst", "technical"):
        return state

    ticker = state['ticker']
    horizon = state.get('horizon') or state.get('run_config', {}).get('horizon', 'short')
    horizon_days = state.get('horizon_days') or state.get('run_config', {}).get('horizon_days', 10)

    short_horizon_focus = (
        f'TRADING HORIZON: {horizon_days} days (short-term). Focus on: SMA crossovers '
        '(10/20-day), RSI momentum, MACD signal line, recent volume spikes, nearest '
        'support/resistance levels. Identify the dominant current setup, not every possible '
        'reversal path. Ignore 200-day SMA for entry timing. Apply the same confirmation '
        'standard to bullish and bearish setups.'
    )

    # Horizon-specific technical focus
    _TECHNICAL_HORIZON_FOCUS = {
        'short': short_horizon_focus,
        'medium': f'TRADING HORIZON: {horizon_days} days (medium-term). Focus on: 20/50-day SMA trend, RSI trend direction, MACD histogram, key chart patterns (flags, wedges). Balance short and medium momentum.',
        'long': f'TRADING HORIZON: {horizon_days} days (long-term). Focus on: 50/200-day SMA, long-term trend channel, volume trend, major support/resistance zones. Short-term noise is less relevant.',
    }
    horizon_focus = _TECHNICAL_HORIZON_FOCUS.get(horizon, _TECHNICAL_HORIZON_FOCUS['short'])

    # 1. Get the technical data using the tools
    simulated_date = state.get("simulated_date") or state.get("run_config", {}).get("simulated_date")
    price_data = get_historical_price_data(ticker, "1y", as_of=simulated_date)
    indicators = calculate_technical_indicators(price_data)

    # Surface key price levels for UI display (market_snapshot)
    state['market_snapshot'] = {
        "current_price": indicators.get("current_price"),
        "sma_20": indicators.get("SMA_20"),
        "sma_50": indicators.get("SMA_50"),
    }

    # 2. Construct the prompt for the LLM
    prompt = f"""Technical analysis for {ticker}.

Horizon: {horizon_days} trading days.
{horizon_focus}

Your objective is to determine which side (buyers or sellers) has active technical control right now.
Evaluate the dominant setup using trend, momentum, volume, and key actionable levels.
Apply the same strict confirmation standard to both bullish breakouts and bearish breakdowns.
Use the provided indicators strictly. Focus on clear signals and confirmed moves rather than extrapolating premature reversals or over-analyzing minor pullbacks.
If the setup is mixed, identify which side has the slight technical edge. Use NEUTRAL only if the indicators are perfectly balanced without any clear directional control.
If required indicators are missing, write UNKNOWN.

Data:
Technical Indicators: {indicators}

Output exactly:
1) EVIDENCE: 3 bullets (indicator -> current reading -> implication for the active setup now)
2) SUPPORT: value or UNKNOWN
3) RESISTANCE: value or UNKNOWN
4) FINAL_VIEW: BULLISH|BEARISH|NEUTRAL
5) CONFIDENCE: HIGH|MEDIUM|LOW
6) KEY_UNCERTAINTY: one line (single strongest technical reason the active setup may fail soon; avoid generic "could bounce" or "could break out" wording unless directly supported by current indicators)

Keep under 160 words."""
    
    # 3. Call the LLM to generate the analysis (low temperature: factual indicators, not creativity)
    analysis_report = call_llm(prompt, temperature=0.3, call_name="Technical_Analyst")

    # 4. Extract structured signal (zero extra LLM calls — keyword scoring)
    technical_signal, parse_meta = _extract_analyst_signal(analysis_report)
    state['signals']['technical'] = technical_signal
    _record_signal_parse_provenance(state, "technical", parse_meta)

    # 5. Update the state
    state['reports']['technical_analyst'] = analysis_report
    # state['stock_chart_image'] = chart_image_url # Removed legacy chart reference

    return state

def sentiment_analyst_agent(state: dict):
    """Sentiment Analyst Agent - Placeholder (social media APIs unavailable)."""
    ticker = state['ticker']
    
    # Social media integration disabled - APIs unreliable/unavailable
    placeholder_report = f"""Social media sentiment analysis for {ticker} is currently unavailable. 
StockTwits API closed to new registrations and Twitter scraping is unreliable. 
Recommend relying on news sentiment and fundamental/technical analysis instead."""
    
    # NOTE: sentiment placeholder intentionally NOT added to state['reports'].
    # The 'API unavailable' text was injecting noise into Bull/Bear debate prompts,
    # causing researchers to debate a message about missing APIs instead of the stock.
    state['sentiment_metrics'] = {'bullish_pct': 0, 'bearish_pct': 0, 'neutral_pct': 0, 'total': 0}
    
    return state

def news_harvester_agent(state: dict):
    """
    The News Harvester Agent using Finnhub company news.
    Finnhub free tier does not provide native sentiment, so the news tool attaches
    a lightweight heuristic tone score/label for downstream consistency.
    """
    if _has_cached_analyst_output(state, "news_harvester", "news"):
        return state

    
    ticker = state['ticker']
    
    # Get news with unified 14-day lookback (independent of horizon for consistency).
    # This ensures all experiments use the same news window regardless of forward-looking k.
    UNIFIED_LOOKBACK_DAYS = 14
    simulated_date = state.get("simulated_date") or state.get("run_config", {}).get("simulated_date")
    horizon = state.get("horizon") or state.get("run_config", {}).get("horizon", "short")
    
    articles = search_news(ticker, limit=50, as_of=simulated_date, lookback_days=UNIFIED_LOOKBACK_DAYS)
    
    # 2. Store in shared context for other agents to reuse
    shared_context.set(f'news_articles_{ticker}', articles)
    
    print(f"[SHARED CONTEXT] News Harvester stored {len(articles)} news articles for {ticker}")

    # 2.1 Provenance/debug block for UI verification (compact)
    from datetime import datetime, timedelta

    def _parse_published(value: str):
        if not value:
            return None
        v = value.strip()
        # Support legacy AlphaVantage formats e.g. 20250103T153000/20250103T1530
        for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
            try:
                return datetime.strptime(v, fmt)
            except ValueError:
                continue
        # Finnhub tool returns ISO-8601 strings
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None

    as_of_dt = None
    if simulated_date:
        try:
            as_of_dt = datetime.fromisoformat(simulated_date)
        except ValueError:
            try:
                as_of_dt = datetime.fromisoformat(simulated_date.split("T")[0])
            except ValueError:
                as_of_dt = None

    window_start = (as_of_dt - timedelta(days=UNIFIED_LOOKBACK_DAYS)).date().isoformat() if as_of_dt else None
    window_end = as_of_dt.date().isoformat() if as_of_dt else None

    parsed_times = [t for t in (_parse_published(a.get("published", "")) for a in articles) if t is not None]
    min_pub = min(parsed_times).isoformat() if parsed_times else None
    max_pub = max(parsed_times).isoformat() if parsed_times else None

    compact_articles = []
    for a in articles[:10]:
        compact_articles.append(
            {
                "title": a.get("title", ""),
                "source": a.get("source", ""),
                "published": a.get("published", ""),
                "url": a.get("url", ""),
                "ticker_sentiment_label": a.get("ticker_sentiment_label", ""),
                "ticker_sentiment_score": a.get("ticker_sentiment_score", 0),
                "relevance_score": a.get("relevance_score", 0),
            }
        )

    if 'provenance' not in state:
        state['provenance'] = {}
    state['provenance']['news'] = {
        'ticker': ticker,
        'as_of': simulated_date,
        'lookback_days': UNIFIED_LOOKBACK_DAYS,
        'window_start': window_start,
        'window_end': window_end,
        'article_count': len(articles),
        'min_published': min_pub,
        'max_published': max_pub,
        'articles': compact_articles,
    }
    
    print(f"[NEWS PROVENANCE] Added to state: as_of={simulated_date}, horizon={horizon}, lookback={UNIFIED_LOOKBACK_DAYS}d (unified), window={window_start} to {window_end}, articles={len(articles)}, published range={min_pub} to {max_pub}")
    
    # 3. Format news with sentiment for LLM
    news_summary = f"News Analysis for {ticker} ({len(articles)} articles):\n\n"
    
    for i, article in enumerate(articles[:10], 1):  # Top 10 articles
        news_summary += f"{i}. [{article.get('ticker_sentiment_label', 'Neutral')}] {article.get('title', '')}\n"
        news_summary += (
            "   Source: {source} | Tone: {score:.2f} | Relevance: {rel:.2f}\n".format(
                source=article.get('source', ''),
                score=float(article.get('ticker_sentiment_score', 0.0) or 0.0),
                rel=float(article.get('relevance_score', 0.0) or 0.0),
            )
        )
        news_summary += f"   Summary: {article.get('summary', '')}\n\n"
    
    # Calculate average sentiment
    if articles:
        avg_sentiment = sum(float(a.get('ticker_sentiment_score', 0.0) or 0.0) for a in articles) / len(articles)
        bullish_count = sum(1 for a in articles if 'Bullish' in (a.get('ticker_sentiment_label') or ''))
        bearish_count = sum(1 for a in articles if 'Bearish' in (a.get('ticker_sentiment_label') or ''))
    else:
        avg_sentiment = 0.0
        bullish_count = 0
        bearish_count = 0
    
    # Horizon-specific news focus
    horizon_days = state.get('horizon_days') or state.get('run_config', {}).get('horizon_days', 10)
    _NEWS_HORIZON_FOCUS = {
        'short': f'TRADING HORIZON: {horizon_days} days. Prioritise: news from the last 3-5 days, earnings announcements, analyst upgrades/downgrades, product launches. Flag any event that could move the price within {horizon_days} days.',
        'medium': f'TRADING HORIZON: {horizon_days} days. Prioritise: earnings trends, macro headwinds, sector news, regulatory updates. Weight recent news more but also note scheduled events in the coming weeks.',
        'long': f'TRADING HORIZON: {horizon_days} days. Prioritise: structural trends, management changes, multi-quarter revenue trends, industry disruption signals. Recent daily news is less relevant than sustained narrative shifts.',
    }
    horizon_focus = _NEWS_HORIZON_FOCUS.get(horizon, _NEWS_HORIZON_FOCUS['short'])

    # 4. Construct the prompt for the LLM
    prompt = f"""News analysis for {ticker}.

Horizon: {horizon_days} trading days.
{horizon_focus}

Your objective is to extract ticker-specific, near-term catalysts from the provided articles.
Filter out broad sector chatter, thematic narratives, and generic company mentions unless they explicitly provide a transmission path to move the stock price within {horizon_days} trading days.
Weigh both positive and negative news based on their concrete market impact.
If the news is mixed, identify which side has the slight edge. Remain NEUTRAL only if the news is purely ambient noise without any actionable direction.
Base your analysis entirely on the provided articles.

{news_summary}

Sentiment stats:
- Average score: {avg_sentiment:.2f}
- Bullish count: {bullish_count}
- Bearish count: {bearish_count}

Output exactly:
1) CATALYSTS: 0 to 2 crisp bullets maximum (active ticker-specific event/signal -> why it can move price soon). Only include a bullet if there is a specific near-term catalyst. If none, write "None identified."
2) TONE: BULLISH|BEARISH|NEUTRAL
3) FINAL_VIEW: BULLISH|BEARISH|NEUTRAL
4) CONFIDENCE: HIGH|MEDIUM|LOW
5) KEY_EVENT_RISK: one single sentence (use "N/A" if none).

Keep it brutally concise. Do not use filler words."""
    
    # 5. Call the LLM to generate the analysis (low temperature: factual news reporting)
    analysis_report = call_llm(prompt, temperature=0.3, call_name="News_Harvester")

    # 6. Extract structured signal (zero extra LLM calls — keyword scoring)
    news_signal, parse_meta = _extract_analyst_signal(analysis_report)
    state['signals']['news'] = news_signal
    _record_signal_parse_provenance(state, "news", parse_meta)

    # 7. Update the state
    state['reports']['news_harvester'] = analysis_report
    state['news_sentiment'] = {
        'average_score': avg_sentiment,
        'bullish_count': bullish_count,
        'bearish_count': bearish_count,
    }
    
    return state