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
# from ..graph.state import AgentState # We will define this later


def _extract_analyst_signal(analysis_text: str) -> dict:
    """
    Extract a structured directional signal from analyst prose using keyword scoring.

    Zero extra LLM calls — uses frequency counting of bullish/bearish keywords.
    Purpose: give debate agents a quick orientation (e.g. 'BEARISH 72%') before
    reading 300 words of prose, fixing the 'raw dict dump' problem in prompts.
    """
    text = analysis_text.lower()

    bullish_kw = [
        'bullish', 'buy', 'uptrend', 'golden cross', 'strong', 'positive momentum',
        'growth', 'outperform', 'upside', 'accumulate', 'beat', 'surge', 'rally',
        'breakout', 'record high', 'upgrade', 'above',
    ]
    bearish_kw = [
        'bearish', 'sell', 'downtrend', 'death cross', 'weak', 'negative', 'declining',
        'underperform', 'downside', 'avoid', 'miss', 'drop', 'breakdown',
        'concern', 'warning', 'downgrade', 'below', 'pressure', 'risk',
    ]

    bull_score = sum(text.count(kw) for kw in bullish_kw)
    bear_score = sum(text.count(kw) for kw in bearish_kw)
    total = bull_score + bear_score

    if total == 0:
        return {'direction': 'NEUTRAL', 'confidence': 0.5, 'key_factor': 'No clear directional signals'}
    if bull_score > bear_score:
        confidence = round(min(0.9, 0.5 + (bull_score - bear_score) / max(total, 1) * 0.5), 2)
        return {'direction': 'BULLISH', 'confidence': confidence, 'key_factor': f'{bull_score} bullish vs {bear_score} bearish signals'}
    elif bear_score > bull_score:
        confidence = round(min(0.9, 0.5 + (bear_score - bull_score) / max(total, 1) * 0.5), 2)
        return {'direction': 'BEARISH', 'confidence': confidence, 'key_factor': f'{bear_score} bearish vs {bull_score} bullish signals'}
    return {'direction': 'NEUTRAL', 'confidence': 0.5, 'key_factor': 'Balanced bullish/bearish signals'}


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
    prompt = f"""Conduct a fundamental analysis of {ticker}.

{horizon_focus}

Data provided:
Financial Statements: {financial_statements}
Financial Ratios: {financial_ratios}
Analyst Ratings: {analyst_ratings}

Analyze (prioritise factors most relevant to the {horizon_days}-day horizon above):
- Financial health: profitability, liquidity, solvency, efficiency
- Red flags or concerns
- Overall assessment

FORMAT: Use Markdown with `### Headers` and `- Bullet points`.
Structure:
- **Top 3 Fundamental Facts for This Horizon**: strongest evidence only (numbers first).
- **Risk Flags**: 1-2 concrete downside flags.
- **Conclusion**: one-line stance (Bullish/Bearish/Neutral) for the {horizon_days}-day horizon.

Keep response structured and under 220 words."""
    
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
        'short': f'TRADING HORIZON: {horizon_days} days (short-term). Focus on: SMA crossovers (10/20-day), RSI momentum, MACD signal line, recent volume spikes, nearest support/resistance levels. Ignore 200-day SMA for entry timing.',
        'medium': f'TRADING HORIZON: {horizon_days} days (medium-term). Focus on: 20/50-day SMA trend, RSI trend direction, MACD histogram, key chart patterns (flags, wedges). Balance short and medium momentum.',
        'long': f'TRADING HORIZON: {horizon_days} days (long-term). Focus on: 50/200-day SMA, long-term trend channel, volume trend, major support/resistance zones. Short-term noise is less relevant.',
    }
    horizon_focus = _TECHNICAL_HORIZON_FOCUS.get(horizon, _TECHNICAL_HORIZON_FOCUS['short'])

    # 1. Get the technical data using the tools
    simulated_date = state.get("simulated_date") or state.get("run_config", {}).get("simulated_date")
    price_data = get_historical_price_data(ticker, "1y", as_of=simulated_date)
    indicators = calculate_technical_indicators(price_data)

    # 2. Construct the prompt for the LLM
    prompt = f"""Perform technical analysis of {ticker}.

{horizon_focus}

Data provided:
Technical Indicators: {indicators}

Analyze (weight indicators by their relevance to the {horizon_days}-day horizon above):
- Price trends, support/resistance levels, chart patterns
- Key technical indicators
- Trading volume strength
- Price forecast for the next {horizon_days} trading days

FORMAT: Use Markdown with `### Headers` and `- Bullet points`.
Structure:
- **Top 3 Technical Facts for This Horizon**: strongest signals only.
- **Key Levels**: nearest support/resistance levels.
- **Forecast**: one-line {horizon_days}-day outlook (Bullish/Bearish/Neutral).

Keep response structured and under 260 words."""
    
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
    prompt = f"""Analyze latest news for {ticker}.

{horizon_focus}

{news_summary}

News Sentiment Summary:
- Average Sentiment Score: {avg_sentiment:.2f} (-1 bearish to +1 bullish)
- Bullish articles: {bullish_count}
- Bearish articles: {bearish_count}

Provide (prioritise catalysts most likely to impact price in the next {horizon_days} days):
- Key catalysts and events
- Sentiment trend assessment
- Market-moving developments
- Risk factors from news

FORMAT: Use Markdown with `### Headers` and `- Bullet points`.
Structure:
- **Top 3 News Catalysts for This Horizon**: concrete, dated catalysts only.
- **Sentiment**: summary of tone (Bullish/Bearish/Neutral).
- **Risks**: 1-2 event risks that could invalidate the thesis.
- **Market Impact**: one-line likely {horizon_days}-day price direction.

Keep response structured and under 220 words."""
    
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