# In nexustrader/backend/test_fundamental_data.py
import yfinance as yf
import pandas as pd

def test_nvda_financials():
    """
    A standalone test to fetch and display financial data for NVDA
    to verify the years being pulled by the yfinance library.
    """
    ticker_symbol = "AAPL"
    print(f"--- Fetching financial data for {ticker_symbol} ---")
    
    try:
        # This is the same library our agent's tool uses
        nvda = yf.Ticker(ticker_symbol)
        
        # 1. Fetch Annual Income Statement
        print("\n--- Annual Income Statement ---")
        income_stmt = nvda.income_stmt
        if not income_stmt.empty:
            # yfinance returns columns with dates. We'll display the column headers.
            print("Available years (columns):")
            print([col.strftime('%Y-%m-%d') for col in income_stmt.columns])
            # Display a few key rows
            print("\nSample Data (Total Revenue):")
            print(income_stmt.loc['Total Revenue'])
        else:
            print("No annual income statement data found.")

        # 2. Fetch Annual Balance Sheet
        print("\n--- Annual Balance Sheet ---")
        balance_sheet = nvda.balance_sheet
        if not balance_sheet.empty:
            print("Available years (columns):")
            print([col.strftime('%Y-%m-%d') for col in balance_sheet.columns])
            print("\nSample Data (Total Assets):")
            print(balance_sheet.loc['Total Assets'])
        else:
            print("No annual balance sheet data found.")
            
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    # To prevent yfinance from printing too much, we'll set a specific format
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    test_nvda_financials()
