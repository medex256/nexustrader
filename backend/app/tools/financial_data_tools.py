# In nexustrader/backend/app/tools/financial_data_tools.py
import yfinance as yf
import json

def get_financial_statements(ticker: str):
    """
    Returns the company's income statement, balance sheet, and cash flow statement.
    """
    print(f"Fetching financial statements for {ticker}...")
    stock = yf.Ticker(ticker)
    
    # Convert DataFrames to JSON strings for LLM processing
    income_statement = stock.financials.to_json()
    balance_sheet = stock.balance_sheet.to_json()
    cash_flow = stock.cashflow.to_json()
    
    return {
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cash_flow_statement": cash_flow,
    }

def get_financial_ratios(ticker: str):
    """
    Returns a dictionary of key financial ratios.
    """
    print(f"Fetching financial ratios for {ticker}...")
    stock_info = yf.Ticker(ticker).info
    
    # Extract a selection of key ratios
    ratios = {
        "trailing_pe": stock_info.get("trailingPE"),
        "forward_pe": stock_info.get("forwardPE"),
        "price_to_sales": stock_info.get("priceToSalesTrailing12Months"),
        "price_to_book": stock_info.get("priceToBook"),
        "enterprise_to_revenue": stock_info.get("enterpriseToRevenue"),
        "enterprise_to_ebitda": stock_info.get("enterpriseToEbitda"),
        "profit_margins": stock_info.get("profitMargins"),
        "return_on_equity": stock_info.get("returnOnEquity"),
        "debt_to_equity": stock_info.get("debtToEquity"),
        "current_ratio": stock_info.get("currentRatio"),
    }
    # Filter out any None values
    return {k: v for k, v in ratios.items() if v is not None}

def get_analyst_ratings(ticker: str):
    """
    Returns a summary of analyst ratings for the stock.
    """
    print(f"Fetching analyst ratings for {ticker}...")
    stock = yf.Ticker(ticker)
    
    # Convert recommendations DataFrame to JSON
    recommendations = stock.recommendations.to_json()
    
    return {"recommendations": recommendations}

def get_key_valuation_metrics(ticker: str):
    """
    Returns a dictionary of key valuation metrics.
    """
    print(f"Fetching key valuation metrics for {ticker}...")
    stock_info = yf.Ticker(ticker).info
    
    metrics = {
        "market_cap": stock_info.get("marketCap"),
        "enterprise_value": stock_info.get("enterpriseValue"),
        "trailing_pe": stock_info.get("trailingPE"),
        "forward_pe": stock_info.get("forwardPE"),
        "peg_ratio": stock_info.get("pegRatio"),
        "price_to_sales": stock_info.get("priceToSalesTrailing12Months"),
        "price_to_book": stock_info.get("priceToBook"),
        "enterprise_to_revenue": stock_info.get("enterpriseToRevenue"),
        "enterprise_to_ebitda": stock_info.get("enterpriseToEbitda"),
    }
    return {k: v for k, v in metrics.items() if v is not None}

def get_competitor_list(ticker: str):
    """
    Returns a list of the company's main competitors.

    NOTE: This is a placeholder function.
    """
    print(f"Fetching competitor list for {ticker}...")
    return ["Dummy Competitor 1", "Dummy Competitor 2"]