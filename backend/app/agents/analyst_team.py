# In nexustrader/backend/app/agents/analyst_team.py

from ..tools.financial_data_tools import get_financial_statements, get_financial_ratios, get_analyst_ratings
from ..tools.technical_analysis_tools import get_historical_price_data, calculate_technical_indicators, plot_stock_chart
from ..tools.social_media_tools import search_twitter, search_reddit, search_stocktwits, analyze_sentiment, identify_influencers
from ..tools.news_tools import search_news, summarize_article, filter_news_by_relevance
# from ..graph.state import AgentState # We will define this later

# This is a placeholder for the actual LLM call
def call_llm(prompt: str):
    print("---")
    print("Calling LLM with prompt:")
    print(prompt)
    print("---")
    return "This is a dummy response from the LLM."

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
    prompt = f"""
Your mission is to conduct a thorough fundamental analysis of the stock {ticker}.
You have been provided with the following information:

Financial Statements:
{financial_statements}

Financial Ratios:
{financial_ratios}

Analyst Ratings:
{analyst_ratings}

Please perform the following tasks:
1.  Analyze the company's financial statements.
2.  Assess the company's profitability, liquidity, solvency, and efficiency.
3.  Identify any potential red flags or areas of concern in the company's financials.
4.  Summarize your findings in a comprehensive report.
"""
    
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
    chart_image = plot_stock_chart(price_data, indicators)
    
    # 2. Construct the prompt for the LLM
    prompt = f"""
Your mission is to perform a technical analysis of the stock {ticker}.
You have been provided with the following information:

Technical Indicators:
{indicators}

Stock Chart:
{chart_image}

Please perform the following tasks:
1.  Analyze the stock's price chart to identify key trends, support and resistance levels, and chart patterns.
2.  Interpret the key technical indicators.
3.  Analyze the stock's trading volume to gauge the strength of price movements.
4.  Formulate a short-term price forecast based on your analysis.
5.  Summarize your findings in a comprehensive report.
"""
    
    # 3. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 4. Update the state
    state['reports']['technical_analyst'] = analysis_report
    state['stock_chart_image'] = chart_image
    
    return state

def sentiment_analyst_agent(state: dict):
    """
    The Sentiment Analyst Agent.
    """
    ticker = state['ticker']
    
    # 1. Get the social media data using the tools
    twitter_results = search_twitter(ticker)
    reddit_results = search_reddit("wallstreetbets", ticker)
    stocktwits_results = search_stocktwits(ticker)
    
    # 2. Analyze the sentiment
    sentiment_score = analyze_sentiment(f"{twitter_results}\n{reddit_results}\n{stocktwits_results}")
    
    # 3. Identify influencers
    influencers = identify_influencers("twitter")
    
    # 4. Construct the prompt for the LLM
    prompt = f"""
Your mission is to analyze the social media sentiment for the stock {ticker}.
You have been provided with the following information:

Twitter Mentions:
{twitter_results}

Reddit Mentions (r/wallstreetbets):
{reddit_results}

StockTwits Mentions:
{stocktwits_results}

Overall Sentiment Score: {sentiment_score}
Key Influencers: {influencers}

Please perform the following tasks:
1.  Summarize the key themes and narratives being discussed on social media.
2.  Provide an overall assessment of the social media sentiment.
3.  Summarize your findings in a comprehensive report.
"""
    
    # 5. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 6. Update the state
    state['reports']['sentiment_analyst'] = analysis_report
    state['sentiment_score'] = sentiment_score
    
    return state

def news_harvester_agent(state: dict):
    """
    The News Harvester Agent. check
    """
    ticker = state['ticker']
    
    # 1. Get the news using the tools
    articles = search_news(ticker)
    relevant_articles = filter_news_by_relevance(articles)
    
    summaries = []
    for article in relevant_articles:
        summaries.append(summarize_article(article))
        
    # 2. Construct the prompt for the LLM
    prompt = f"""
Your mission is to gather, filter, and summarize the latest news for the stock {ticker}.
You have been provided with the following summaries of recent news articles:

{summaries}

Please perform the following tasks:
1.  Identify any news that could act as a catalyst for a significant price movement.
2.  Summarize your findings in a concise report.
"""
    
    # 3. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 4. Update the state
    state['reports']['news_harvester'] = analysis_report
    
    return state