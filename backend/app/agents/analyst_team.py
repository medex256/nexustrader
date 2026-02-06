# In nexustrader/backend/app/agents/analyst_team.py

from ..tools.financial_data_tools import get_financial_statements, get_financial_ratios, get_analyst_ratings
from ..tools.technical_analysis_tools import get_historical_price_data, calculate_technical_indicators, plot_stock_chart
from ..tools.news_tools import search_news
from ..llm import invoke_llm as call_llm
from ..utils.shared_context import shared_context
# from ..graph.state import AgentState # We will define this later

def fundamental_analyst_agent(state: dict):
    """
    The Fundamental Analyst Agent.
    """
    ticker = state['ticker']
    
    # 1. Get the financial data using the tools
    financial_statements = get_financial_statements(ticker)
    financial_ratios = get_financial_ratios(ticker)
    analyst_ratings = get_analyst_ratings(ticker)
    
    # 2. Construct the prompt for the LLM
    prompt = f"""Conduct a fundamental analysis of {ticker}.

Data provided:
Financial Statements: {financial_statements}
Financial Ratios: {financial_ratios}
Analyst Ratings: {analyst_ratings}

Analyze:
- Financial health: profitability, liquidity, solvency, efficiency
- Red flags or concerns
- Overall assessment

FORMAT: Use Markdown with `### Headers` and `- Bullet points`.
Structure:
- **Profitability & Efficiency**: Margins, ROE, etc.
- **Solvency & Liquidity**: Debt levels, current ratio.
- **Valuation**: P/E, EV/EBITDA vs peers.
- **Conclusion**: Fundamental strength assessment.

Keep response structured and under 300 words."""
    
    # 3. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 4. Update the state
    if 'reports' not in state:
        state['reports'] = {}
    state['reports']['fundamental_analyst'] = analysis_report
    
    return state

def technical_analyst_agent(state: dict):
    """
    The Technical Analyst Agent.
    """
    ticker = state['ticker']
    
    # 1. Get the technical data using the tools
    simulated_date = state.get("simulated_date") or state.get("run_config", {}).get("simulated_date")
    price_data = get_historical_price_data(ticker, "1y", as_of=simulated_date)
    indicators = calculate_technical_indicators(price_data)
    
    # NOTE: Passive Chart generation removed.
    # The frontend now renders interactive charts via the /api/chart endpoint.
    # The LLM relies on the numerical 'indicators' data below, not a vision model.
    # chart_image_path = plot_stock_chart(price_data, ticker)
    
    # 2. Construct the prompt for the LLM
    prompt = f"""Perform technical analysis of {ticker}.

Data provided:
Technical Indicators: {indicators}

Analyze:
- Price trends, support/resistance levels, chart patterns
- Key technical indicators
- Trading volume strength
- Short-term price forecast

FORMAT: Use Markdown with `### Headers` and `- Bullet points`.
Structure:
- **Trend Analysis**: Moving averages, direction.
- **Momentum**: RSI, MACD signals.
- **Support/Resistance**: Key levels to watch.
- **Forecast**: Short-term outlook (Bullish/Bearish/Neutral).

Keep response structured and under 300 words."""
    
    # 3. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 4. Update the state

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
    
    state['reports']['sentiment_analyst'] = placeholder_report
    state['sentiment_metrics'] = {'bullish_pct': 0, 'bearish_pct': 0, 'neutral_pct': 0, 'total': 0}
    
    return state

def news_harvester_agent(state: dict):
    """
    The News Harvester Agent using Alpha Vantage NEWS_SENTIMENT API.
    Provides news with pre-calculated sentiment scores and article summaries.
    """
    from ..tools.news_tools import search_news_alpha_vantage
    
    ticker = state['ticker']
    
    # 1. Get news with sentiment from Alpha Vantage
    simulated_date = state.get("simulated_date") or state.get("run_config", {}).get("simulated_date")
    articles = search_news_alpha_vantage(ticker, limit=50, as_of=simulated_date, lookback_days=7)
    
    # 2. Store in shared context for other agents to reuse
    shared_context.set(f'news_articles_{ticker}', articles)
    
    print(f"[SHARED CONTEXT] News Harvester stored {len(articles)} news articles for {ticker}")
    
    # 3. Format news with sentiment for LLM
    news_summary = f"News Analysis for {ticker} ({len(articles)} articles):\n\n"
    
    for i, article in enumerate(articles[:10], 1):  # Top 10 articles
        news_summary += f"{i}. [{article['ticker_sentiment_label']}] {article['title']}\n"
        news_summary += f"   Source: {article['source']} | Sentiment: {article['ticker_sentiment_score']:.2f} | Relevance: {article['relevance_score']:.2f}\n"
        news_summary += f"   Summary: {article['summary'][:150]}...\n\n"
    
    # Calculate average sentiment
    if articles:
        avg_sentiment = sum(a['ticker_sentiment_score'] for a in articles) / len(articles)
        bullish_count = sum(1 for a in articles if 'Bullish' in a['ticker_sentiment_label'])
        bearish_count = sum(1 for a in articles if 'Bearish' in a['ticker_sentiment_label'])
    else:
        avg_sentiment = 0
        bullish_count = 0
        bearish_count = 0
    
    # 4. Construct the prompt for the LLM
    prompt = f"""Analyze latest news for {ticker}.

{news_summary}

News Sentiment Summary:
- Average Sentiment Score: {avg_sentiment:.2f} (-1 bearish to +1 bullish)
- Bullish articles: {bullish_count}
- Bearish articles: {bearish_count}

Provide:
- Key catalysts and events
- Sentiment trend assessment  
- Market-moving developments
- Risk factors from news

FORMAT: Use Markdown with `### Headers` and `- Bullet points`.
Structure:
- **Major Catalysts**: Key partnerships, earnings, product launches.
- **Sentiment**: Summary of media tone (Bullish/Bearish).
- **Risks**: Potential headwinds mentioned in news.
- **Market Impact**: Likely short-term price effect.

Keep response structured and under 250 words."""
    
    # 5. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 6. Update the state
    state['reports']['news_harvester'] = analysis_report
    state['news_sentiment'] = {
        'average_score': avg_sentiment,
        'bullish_count': bullish_count,
        'bearish_count': bearish_count,
    }
    
    return state