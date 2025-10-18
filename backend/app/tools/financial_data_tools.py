# In nexustrader/backend/app/tools/financial_data_tools.py

def get_financial_statements(ticker: str):
    """
    Returns the company's income statement, balance sheet, and cash flow statement for the last 5 years.
    
    NOTE: This is a placeholder function. We will implement the actual data fetching logic later.
    """
    print(f"Fetching financial statements for {ticker}...")
    # In a real implementation, this function would call a financial data API (e.g., yfinance, Alpha Vantage)
    # For now, we will return some dummy data.
    return {
        "income_statement": "Dummy Income Statement",
        "balance_sheet": "Dummy Balance Sheet",
        "cash_flow_statement": "Dummy Cash Flow Statement",
    }

def get_financial_ratios(ticker: str):
    """
    Returns a dictionary of key financial ratios.

    NOTE: This is a placeholder function.
    """
    print(f"Fetching financial ratios for {ticker}...")
    return {"p_e_ratio": "N/A"}

def get_analyst_ratings(ticker: str):
    """
    Returns a summary of analyst ratings for the stock.

    NOTE: This is a placeholder function.
    """
    print(f"Fetching analyst ratings for {ticker}...")
    return {"rating": "N/A"}

def get_key_valuation_metrics(ticker: str):
    """
    Returns a dictionary of key valuation metrics.

    NOTE: This is a placeholder function.
    """
    print(f"Fetching key valuation metrics for {ticker}...")
    return {"p_b_ratio": "N/A"}

def get_competitor_list(ticker: str):
    """
    Returns a list of the company's main competitors.

    NOTE: This is a placeholder function.
    """
    print(f"Fetching competitor list for {ticker}...")
    return ["Dummy Competitor 1", "Dummy Competitor 2"]