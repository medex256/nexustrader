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


def _extract_analyst_signal(analysis_text: str) -> dict:
    """
    Extract a structured directional signal by parsing the labelled output fields
    that analyst prompts already produce (FINAL_VIEW, CONFIDENCE, etc.).

    Replaces the old keyword-frequency counting approach, which was unreliable
    because "not bullish" had the same weight as "strongly bullish".
    Zero extra LLM calls — pure regex on the structured analyst output.
    """
    # --- Direction: FINAL_VIEW field (all three analyst prompts output this) ---
    direction = "NEUTRAL"
    _direction_parsed = False
    view_match = re.search(r"FINAL_VIEW\s*:\s*(BULLISH|BEARISH|NEUTRAL)", analysis_text, flags=re.IGNORECASE)
    if view_match:
        direction = view_match.group(1).upper()
        _direction_parsed = True
    else:
        # Fallback: TONE field (news analyst also outputs this)
        tone_match = re.search(r"\bTONE\s*:\s*(BULLISH|BEARISH|NEUTRAL)", analysis_text, flags=re.IGNORECASE)
        if tone_match:
            direction = tone_match.group(1).upper()
            _direction_parsed = True

    # --- Confidence: CONFIDENCE field ---
    confidence_level = "MEDIUM"
    _confidence_parsed = False
    conf_match = re.search(r"\bCONFIDENCE\s*:\s*(HIGH|MEDIUM|LOW)", analysis_text, flags=re.IGNORECASE)
    if conf_match:
        confidence_level = conf_match.group(1).upper()
        _confidence_parsed = True

    # Log parse misses so we can monitor format-compliance rate
    if not _direction_parsed or not _confidence_parsed:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "[signal_extract] Parse miss — direction_found=%s confidence_found=%s | "
            "text_snippet=%.120s",
            _direction_parsed, _confidence_parsed,
            analysis_text.replace("\n", " "),
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
    # Match "EVIDENCE:\n  - bullet text" or "CATALYSTS:\n  1) bullet text" patterns
    catalyst_match = re.search(
        r"(?:EVIDENCE|CATALYSTS)\s*:?\s*\n\s*(?:\d+[.)\s]|[-*•]\s*)(.+)",
        analysis_text, flags=re.IGNORECASE
    )
    if catalyst_match:
        key_catalyst = catalyst_match.group(1).strip()[:140]
    else:
        # Inline fallback: "EVIDENCE: some text on same line"
        cat_inline = re.search(r"(?:EVIDENCE|CATALYSTS)\s*:\s*(.+)", analysis_text, flags=re.IGNORECASE)
        if cat_inline:
            key_catalyst = cat_inline.group(1).strip()[:140]

    # --- Primary risk: KEY_UNCERTAINTY or KEY_EVENT_RISK ---
    primary_risk = "No explicit primary risk provided"
    risk_match = re.search(
        r"(?:KEY_UNCERTAINTY|KEY_EVENT_RISK|MAIN_RISK|RISKS?)\s*:\s*(.+)",
        analysis_text, flags=re.IGNORECASE
    )
    if risk_match:
        primary_risk = risk_match.group(1).strip()[:140]

    return {
        "direction": direction,
        "magnitude": magnitude,
        "confidence": confidence,
        "key_factor": f"FINAL_VIEW={direction} CONFIDENCE={confidence_level}",
        "key_catalyst": key_catalyst,
        "primary_risk": primary_risk,
    }


def fundamental_analyst_agent(state: dict):
    """
    The Fundamental Analyst Agent.
    """
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

Use only the provided data. Do not add external facts or numbers.
If data is missing, write UNKNOWN.
Your job is to identify what is ACTIVE and likely to matter within {horizon_days} trading days.
Prefer recent acceleration/deceleration, earnings or guidance change, margin change, liquidity stress, analyst expectation gap, and concrete business change with a short-horizon transmission path into price.
Treat company quality, scale, and older profitability as background unless the data shows they are being repriced now.
Do not invent market reactions. Do not assume post-peak normalization, sentiment fade, or disappointment unless the numbers show live deterioration now.
Recent earnings strength can count only if the change is large enough and still looks actively repriced now.
Historical seasonality or an expected giveback after a peak quarter is background unless current data already confirms the slowdown.
If the evidence is mostly background quality plus one vague concern, stay neutral rather than forcing a directional edge.

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
    analysis_report = call_llm(prompt, temperature=0.3)

    # 4. Extract structured signal (zero extra LLM calls — keyword scoring)
    if 'signals' not in state:
        state['signals'] = {}
    state['signals']['fundamental'] = _extract_analyst_signal(analysis_report)

    # 5. Update the state
    if 'reports' not in state:
        state['reports'] = {}
    state['reports']['fundamental_analyst'] = analysis_report

    return state

def technical_analyst_agent(state: dict):
    """
    The Technical Analyst Agent.
    """
    ticker = state['ticker']
    horizon = state.get('horizon') or state.get('run_config', {}).get('horizon', 'short')
    horizon_days = state.get('horizon_days') or state.get('run_config', {}).get('horizon_days', 10)

    # Horizon-specific technical focus
    _TECHNICAL_HORIZON_FOCUS = {
        'short': f'TRADING HORIZON: {horizon_days} days (short-term). Focus on: SMA crossovers (10/20-day), RSI momentum, MACD signal line, recent volume spikes, nearest support/resistance levels. Identify the dominant current setup, not every possible reversal path. Ignore 200-day SMA for entry timing. Treat bearish technical setups as high-conviction only when weakness is confirmed, not when it is just a normal pullback or one soft signal.',
        'medium': f'TRADING HORIZON: {horizon_days} days (medium-term). Focus on: 20/50-day SMA trend, RSI trend direction, MACD histogram, key chart patterns (flags, wedges). Balance short and medium momentum.',
        'long': f'TRADING HORIZON: {horizon_days} days (long-term). Focus on: 50/200-day SMA, long-term trend channel, volume trend, major support/resistance zones. Short-term noise is less relevant.',
    }
    horizon_focus = _TECHNICAL_HORIZON_FOCUS.get(horizon, _TECHNICAL_HORIZON_FOCUS['short'])

    # 1. Get the technical data using the tools
    simulated_date = state.get("simulated_date") or state.get("run_config", {}).get("simulated_date")
    price_data = get_historical_price_data(ticker, "1y", as_of=simulated_date)
    indicators = calculate_technical_indicators(price_data)

    # 2. Construct the prompt for the LLM
    prompt = f"""Technical analysis for {ticker}.

Horizon: {horizon_days} trading days.
{horizon_focus}

Use only the provided indicators. Do not invent values.
If missing, write UNKNOWN.
Describe the current technical state, not all hypothetical scenarios.
Prioritise what is active now: trend, momentum, volume confirmation, and the nearest actionable level.
If the setup is mixed, still identify which side currently has more technical control.
Separate active seller/buyer control from routine caution.
Do not turn every support or resistance level into a forecast.
Do not call the setup BULLISH just because price reclaimed one level if the move is not confirmed.
Do not call the setup BEARISH from one weak signal alone.
For a bullish read, prefer confirmed reclaim, positive MACD alignment, sustained price above key averages, and room for continuation.
For a bearish read, prefer confirmed breakdown, price staying below key averages, negative MACD alignment with weak momentum, or downside follow-through with seller control.
Low volume, nearby resistance, overbought cooling, oversold bounce risk, or one crossover should usually lower confidence rather than create a full opposite thesis.

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
    analysis_report = call_llm(prompt, temperature=0.3)

    # 4. Extract structured signal (zero extra LLM calls — keyword scoring)
    state['signals']['technical'] = _extract_analyst_signal(analysis_report)

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

Use only the articles shown. Do not add outside facts.
Do not infer events unless explicitly stated.
Focus on ticker-specific, near-term catalysts only.
Treat broad sector mood, generic AI narrative, ETF holdings pages, and indirect ecosystem news as background. Do not list them as catalysts unless the article clearly explains why they will move {ticker} within {horizon_days} trading days.
Your job is to identify ACTIVE news drivers. A company mention, brand-strength story, or thematic article is not enough unless there is a clear near-term price mechanism.
Do not convert vague market interpretation into a catalyst. If an article does not show a direct company-specific event or near-term transmission path, treat it as background.
If the news is mostly ambient narrative with no live company-specific trigger, stay neutral.

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
    analysis_report = call_llm(prompt, temperature=0.3)

    # 6. Extract structured signal (zero extra LLM calls — keyword scoring)
    state['signals']['news'] = _extract_analyst_signal(analysis_report)

    # 7. Update the state
    state['reports']['news_harvester'] = analysis_report
    state['news_sentiment'] = {
        'average_score': avg_sentiment,
        'bullish_count': bullish_count,
        'bearish_count': bearish_count,
    }
    
    return state