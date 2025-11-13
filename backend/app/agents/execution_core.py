# In nexustrader/backend/app/agents/execution_core.py

from ..tools.derivatives_tools import get_option_chain, calculate_put_call_parity
from ..tools.financial_data_tools import get_financial_statements, get_key_valuation_metrics, get_competitor_list, get_analyst_ratings
from ..tools.social_media_tools import search_twitter, search_reddit
from ..tools.news_tools import search_news
from ..tools.market_data_tools import get_market_sentiment
from ..llm import invoke_llm as call_llm
from ..utils.shared_context import shared_context


def trading_strategy_synthesizer_agent(state: dict):
    """
    The Trading Strategy Synthesizer Agent.
    Now uses the investment_plan from the Research Manager.
    """
    # Get the investment plan from research manager
    investment_plan = state.get('investment_plan', '')
    
    # Fallback to direct arguments if investment_plan not available
    if not investment_plan:
        arguments = state.get('arguments', {})
        bullish = arguments.get('bullish', '')
        bearish = arguments.get('bearish', '')
        context = f"Bullish Argument:\n{bullish}\n\nBearish Argument:\n{bearish}"
    else:
        context = f"Research Manager's Investment Plan:\n{investment_plan}"
    
    # 1. Construct the prompt for the LLM
    prompt = f"""
Your mission is to create a clear and actionable trading strategy based on the research analysis.

{context}

Please perform the following tasks:
1.  Analyze the investment recommendation and rationale.
2.  Formulate a single, decisive trading strategy. The strategy must be one of: BUY, SELL, or HOLD.
3.  If the strategy is BUY or SELL, you must specify:
    - Entry price (based on current market price)
    - Take-profit price (target exit)
    - Stop-loss price (risk management)
    - Position sizing recommendation (% of portfolio)
4.  Provide a clear and concise rationale for your decision.
5.  Format your response as JSON with the following structure:
    {{
        "action": "BUY|SELL|HOLD",
        "entry_price": <number>,
        "take_profit": <number>,
        "stop_loss": <number>,
        "position_size_pct": <number>,
        "rationale": "<your reasoning>"
    }}
"""
    
    # 2. Call the LLM to generate the strategy
    strategy_response = call_llm(prompt)
    
    # 3. Parse the LLM response to get the structured strategy
    # TODO: Implement proper JSON parsing with error handling
    # For now, use a placeholder structure
    import re
    import json
    
    try:
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', strategy_response, re.DOTALL)
        if json_match:
            strategy = json.loads(json_match.group())
        else:
            # Fallback to placeholder
            strategy = {
                "action": "HOLD",
                "entry_price": None,
                "take_profit": None,
                "stop_loss": None,
                "position_size_pct": 0,
                "rationale": strategy_response,
            }
    except:
        # If parsing fails, use placeholder
        strategy = {
            "action": "HOLD",
            "entry_price": None,
            "take_profit": None,
            "stop_loss": None,
            "position_size_pct": 0,
            "rationale": strategy_response,
        }
    
    # 4. Update the state
    state['trading_strategy'] = strategy
    
    return state

def arbitrage_trader_agent(state: dict):
    """
    The Arbitrage Trader Agent.
    """
    ticker = state['ticker']
    
    # 1. Get the derivatives data using the tools
    option_chain = get_option_chain(ticker)
    parity_analysis = calculate_put_call_parity(option_chain)
    
    # 2. Construct the prompt for the LLM
    prompt = f"""
Your mission is to identify and formulate a strategy to exploit arbitrage opportunities for the stock {ticker}.
You have been provided with the following information:

Option Chain:
{option_chain}

Put-Call Parity Analysis:
{parity_analysis}

Please perform the following tasks:
1.  Analyze the provided data to identify any arbitrage opportunities.
2.  If an opportunity is identified, formulate a delta-neutral trading strategy to exploit it.
3.  If no arbitrage opportunity is found, report that the market is efficient.
4.  Summarize your findings in a concise report.
"""
    
    # 3. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 4. Update the state
    if 'trader_reports' not in state:
        state['trader_reports'] = {}
    state['trader_reports']['arbitrage'] = analysis_report
    
    return state

def value_trader_agent(state: dict):
    """
    The Value Trader Agent.
    """
    ticker = state['ticker']
    
    # 1. Get the financial data using the tools
    financial_statements = get_financial_statements(ticker)
    valuation_metrics = get_key_valuation_metrics(ticker)
    competitors = get_competitor_list(ticker)
    analyst_ratings = get_analyst_ratings(ticker)
    
    # 2. Construct the prompt for the LLM
    prompt = f"""
Your mission is to determine if the stock {ticker} is a good long-term value investment.
You have been provided with the following information:

Financial Statements:
{financial_statements}

Valuation Metrics:
{valuation_metrics}

Competitor List:
{competitors}

Analyst Ratings:
{analyst_ratings}

Please perform the following tasks:
1.  Analyze the company's financial statements.
2.  Assess the company's competitive advantage (its "moat").
3.  Compare the company's valuation to its historical averages and to its competitors.
4.  Formulate a recommendation on whether to buy, hold, or sell the stock for a long-term value portfolio.
5.  Summarize your findings in a concise report.
"""
    
    # 3. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 4. Update the state
    state['trader_reports']['value'] = analysis_report
    
    return state

def bull_trader_agent(state: dict):
    """
    The Bull Trader Agent.
    Now retrieves social media data from shared context instead of re-fetching.
    """
    ticker = state['ticker']
    
    # 1. Get news (not cached in shared context, needs fresh data)
    news = search_news(ticker)
    
    # 2. Try to retrieve social media data from shared context
    twitter_sentiment = shared_context.get(f'twitter_data_{ticker}')
    reddit_sentiment = shared_context.get(f'reddit_data_{ticker}')
    
    # 3. Fallback to fetching if not in shared context
    if twitter_sentiment is None:
        print(f"[SHARED CONTEXT] Bull Trader: Twitter data not found, fetching...")
        twitter_sentiment = search_twitter(ticker)
    else:
        print(f"[SHARED CONTEXT] Bull Trader: Using cached Twitter data")
    
    if reddit_sentiment is None:
        print(f"[SHARED CONTEXT] Bull Trader: Reddit data not found, fetching...")
        reddit_sentiment = search_reddit("wallstreetbets", ticker)
    else:
        print(f"[SHARED CONTEXT] Bull Trader: Using cached Reddit data")
    
    # 4. Get other data
    technical_analysis_report = state['reports']['technical_analyst']
    market_sentiment = get_market_sentiment()
    
    # 5. Construct the prompt for the LLM
    prompt = f"""
Your mission is to determine if the stock {ticker} is a good candidate for a high-growth, momentum-based trading strategy.
You have been provided with the following information:

News:
{news}

Twitter Sentiment:
{twitter_sentiment}

Reddit Sentiment:
{reddit_sentiment}

Technical Analysis Report:
{technical_analysis_report}

Overall Market Sentiment:
{market_sentiment}

Please perform the following tasks:
1.  Identify potential growth catalysts for the stock.
2.  Analyze the stock's price momentum and trading volume.
3.  Assess the overall market sentiment and risk appetite.
4.  Formulate a trading strategy with a clear entry point, a target price, and a stop-loss level.
5.  Summarize your findings in a concise report.
"""
    
    # 6. Call the LLM to generate the analysis
    analysis_report = call_llm(prompt)
    
    # 7. Update the state
    state['trader_reports']['bull'] = analysis_report
    
    return state