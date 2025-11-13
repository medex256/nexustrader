# In nexustrader/backend/app/agents/analyst_team.py

from ..tools.financial_data_tools import get_financial_statements, get_financial_ratios, get_analyst_ratings
from ..tools.technical_analysis_tools import get_historical_price_data, calculate_technical_indicators, plot_stock_chart
from ..tools.social_media_tools import search_twitter, search_reddit, search_stocktwits, analyze_sentiment, identify_influencers
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

Keep response under 300 words. Be concise and conversational."""
    
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
    price_data = get_historical_price_data(ticker, "1y")
    indicators = calculate_technical_indicators(price_data)
    chart_image_path = plot_stock_chart(price_data, ticker)

    # --- Create a web-accessible URL for the chart ---
    base_url = "http://127.0.0.1:8000"
    # Ensure we use forward slashes for the URL and get just the filename
    chart_image_filename = chart_image_path.replace('\\', '/').split('/')[-1]
    chart_image_url = f"{base_url}/static/charts/{chart_image_filename}"
    
    # 2. Construct the prompt for the LLM
    prompt = f"""Perform technical analysis of {ticker}.

Data provided:
Technical Indicators: {indicators}
Stock Chart: {chart_image_url}

Analyze:
- Price trends, support/resistance levels, chart patterns
- Key technical indicators
- Trading volume strength
- Short-term price forecast

Keep response under 300 words. Be concise and conversational."""
    
    # 3. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 4. Update the state
    state['reports']['technical_analyst'] = analysis_report
    state['stock_chart_image'] = chart_image_url
    
    return state

def sentiment_analyst_agent(state: dict):
    """
    The Sentiment Analyst Agent.
    Now stores social media data in shared context for reuse.
    """
    ticker = state['ticker']
    
    # 1. Get the social media data using the tools
    twitter_results = search_twitter(ticker)
    reddit_results = search_reddit("wallstreetbets", ticker)
    stocktwits_results = search_stocktwits(ticker)
    
    # 2. Store in shared context for other agents to reuse
    shared_context.set(f'twitter_data_{ticker}', twitter_results)
    shared_context.set(f'reddit_data_{ticker}', reddit_results)
    shared_context.set(f'stocktwits_data_{ticker}', stocktwits_results)
    
    print(f"[SHARED CONTEXT] Sentiment Analyst stored social media data for {ticker}")
    
    # 3. Analyze the sentiment
    sentiment_score = analyze_sentiment(f"{twitter_results}\n{reddit_results}\n{stocktwits_results}")
    
    # 4. Identify influencers
    influencers = identify_influencers("twitter")
    
    # 5. Construct the prompt for the LLM
    prompt = f"""Analyze social media sentiment for {ticker}.

Data provided:
Twitter: {twitter_results}
Reddit (r/wallstreetbets): {reddit_results}
StockTwits: {stocktwits_results}
Sentiment Score: {sentiment_score}
Key Influencers: {influencers}

Provide:
- Key themes and narratives being discussed
- Overall sentiment assessment

Keep response under 250 words. Be concise and conversational."""
    
    # 6. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 7. Update the state
    state['reports']['sentiment_analyst'] = analysis_report
    state['sentiment_score'] = sentiment_score
    
    return state

def news_harvester_agent(state: dict):
    """
    The News Harvester Agent. 
    Now stores news data in shared context for reuse.
    """
    ticker = state['ticker']
    
    # 1. Get the news using the tools
    articles = search_news(ticker)
    
    # 2. Store in shared context for other agents to reuse
    shared_context.set(f'news_articles_{ticker}', articles)
    
    print(f"[SHARED CONTEXT] News Harvester stored news articles for {ticker}")
    
    # --- LOGGING FOR TESTING ---
    print("\n--- Fetched News Articles ---")
    for article in articles:
        print(f"- {article['title']}")
    print("---------------------------\n")
    # ---------------------------
        
    # 3. Construct the prompt for the LLM
    prompt = f"""Analyze latest news for {ticker}.

Recent articles:
{articles}

Provide:
- Key points summary
- Significant catalysts for price movement
- Overall sentiment (Positive/Negative/Neutral)

Keep response under 250 words. Be concise and conversational."""
    
    # 4. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 5. Update the state
    state['reports']['news_harvester'] = analysis_report
    
    return state