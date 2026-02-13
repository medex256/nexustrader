"""
Fundamental Data Tools - Hybrid approach for historical and live data.

ARCHITECTURE:
- Historical backtesting (as_of < today): Use frozen Alpha Vantage data (proper point-in-time)
- Live UI (as_of = None): Use yfinance (free, no rate limits, latest data)

This ensures:
1. Experiments use frozen cache with correct historical fundamentals
2. Live UI gets current data without API rate limit concerns
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import Any

import yfinance as yf

from app.utils.cache import cache_data

# ── Cache Location ─────────────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent.parent.parent.parent / "experiments" / "cache" / "fundamentals"


def _load_frozen_fundamentals(ticker: str, function: str) -> dict | None:
    """
    Load frozen fundamental data from disk.
    
    Args:
        ticker: Stock ticker symbol
        function: One of 'income_statement', 'balance_sheet', 'cash_flow'
    
    Returns:
        Full Alpha Vantage response or None if not cached
    """
    cache_file = CACHE_DIR / ticker.upper() / f"{function}.json"
    
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cached = json.load(f)
            return cached.get("data")
    except Exception:
        return None


def _filter_by_date(reports: list[dict], as_of: str | None) -> list[dict]:
    """
    Filter financial reports to only those on or before as_of date.
    
    Args:
        reports: List of annual or quarterly reports with 'fiscalDateEnding'
        as_of: ISO date string (e.g., '2021-11-15'). If None, returns all.
    
    Returns:
        Filtered list of reports, sorted by date descending (most recent first)
    """
    if as_of is None:
        return sorted(reports, key=lambda x: x.get("fiscalDateEnding", ""), reverse=True)
    
    as_of_dt = datetime.fromisoformat(as_of)
    
    filtered = []
    for report in reports:
        fiscal_date = report.get("fiscalDateEnding")
        if fiscal_date:
            try:
                fiscal_dt = datetime.fromisoformat(fiscal_date)
                if fiscal_dt <= as_of_dt:
                    filtered.append(report)
            except ValueError:
                continue
    
    return sorted(filtered, key=lambda x: x.get("fiscalDateEnding", ""), reverse=True)


def _is_historical_date(as_of: str | None) -> bool:
    """Check if as_of is a historical date (not today or None)."""
    if as_of is None:
        return False
    try:
        as_of_date = datetime.fromisoformat(as_of).date()
        return as_of_date < date.today()
    except (ValueError, TypeError):
        return False


def _get_yfinance_live_statements(ticker: str) -> dict[str, Any]:
    """Fetch current income statement from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        financials = stock.financials  # Annual
        quarterly = stock.quarterly_financials
        
        # Convert DataFrame to Alpha Vantage-like format
        annual_reports = []
        if financials is not None and not financials.empty:
            for date_col in financials.columns:
                report = {"fiscalDateEnding": date_col.strftime("%Y-%m-%d")}
                for idx in financials.index:
                    report[str(idx)] = str(financials.loc[idx, date_col])
                annual_reports.append(report)
        
        quarterly_reports = []
        if quarterly is not None and not quarterly.empty:
            for date_col in quarterly.columns:
                report = {"fiscalDateEnding": date_col.strftime("%Y-%m-%d")}
                for idx in quarterly.index:
                    report[str(idx)] = str(quarterly.loc[idx, date_col])
                quarterly_reports.append(report)
        
        return {
def _get_yfinance_live_balance_sheet(ticker: str) -> dict[str, Any]:
    """Fetch current balance sheet from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        balance_sheet = stock.balance_sheet  # Annual
        quarterly = stock.quarterly_balance_sheet
        
        annual_reports = []
        if balance_sheet is not None and not balance_sheet.empty:
            for date_col in balance_sheet.columns:
                report = {"fiscalDateEnding": date_col.strftime("%Y-%m-%d")}
                for idx in balance_sheet.index:
                    report[str(idx)] = str(balance_sheet.loc[idx, date_col])
                annual_reports.append(report)
        
        quarterly_reports = []
        if quarterly is not None and not quarterly.empty:
            for date_col in quarterly.columns:
                report = {"fiscalDateEnding": date_col.strftime("%Y-%m-%d")}
                for idx in quarterly.index:
                    report[str(idx)] = str(quarterly.loc[idx, date_col])
                quarterly_reports.append(report)
        
        return {
            "symbol": ticker,
            "annualReports": annual_reports,
            "quarterlyReports": quarterly_reports,
            "source": "yfinance_live",
        }
    except Exception as e:
        return {
            "symbol": ticker,
            "annualReports": [],
            "quarterlyReports": [],
            "error": f"yfinance fetch failed: {str(e)}",
        }


@cache_data(ttl_seconds=3600)
def get_balance_sheet(ticker: str, as_of: str | None = None) -> dict[str, Any]:
    """
    Get balance sheet for a ticker.
    
    HYBRID APPROACH:
    - If as_of is historical date → Use frozen Alpha Vantage data
    - If as_of is None/today → Use yfinance live
    
    Args:
        ticker: Stock ticker symbol
        as_of: ISO date string for point-in-time data
    
    Returns:
        Balance sheet data with annualReports and quarterlyReports
    """
    if not _is_historical_date(as_of):
        return _get_yfinance_live_balance_sheet(ticker)
    
    data = _load_frozen_fundamentals(ticker, "balance_sheet")
    
    if data is None:
        return {
            "symbol": ticker,
            "annualReports": [],
            "quarterlyReports": [],
            "error": "No cached fundamental data. Run freeze_fundamentals.py first.",
        }
    
    return {
        "symbol": data.get("symbol", ticker),
        "annualReports": _filter_by_date(data.get("annualReports", []), as_of),
        "quarterlyReports": _filter_by_date(data.get("quarterlyReports", []), as_of),
        "source": "alpha_vantage_frozen"ive"
        }
    """
    # For current/live data, use yfinance
    if not _is_historical_date(as_of):
        return _get_yfinance_live_statements(ticker)
    
    # For historical data, use frozen Alpha Vantage
    data = _load_frozen_fundamentals(ticker, "income_statement")
    
    if data is None:
        return {
            "symbol": ticker,
            "annualReports": [],
            "quarterlyReports": [],
            "error": "No cached fundamental data. Run freeze_fundamentals.py first.",
        }
    
    return {
        "symbol": data.get("symbol", ticker),
        "annualReports": _filter_by_date(data.get("annualReports", []), as_of),
        "quarterlyReports": _filter_by_date(data.get("quarterlyReports", []), as_of),
        "source": "alpha_vantage_frozen",
def _get_yfinance_live_cashflow(ticker: str) -> dict[str, Any]:
    """Fetch current cash flow from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        cashflow = stock.cashflow  # Annual
        quarterly = stock.quarterly_cashflow
        
        annual_reports = []
        if cashflow is not None and not cashflow.empty:
            for date_col in cashflow.columns:
                report = {"fiscalDateEnding": date_col.strftime("%Y-%m-%d")}
                for idx in cashflow.index:
                    report[str(idx)] = str(cashflow.loc[idx, date_col])
                annual_reports.append(report)
        
        quarterly_reports = []
        if quarterly is not None and not quarterly.empty:
            for date_col in quarterly.columns:
                report = {"fiscalDateEnding": date_col.strftime("%Y-%m-%d")}
                for idx in quarterly.index:
                    report[str(idx)] = str(quarterly.loc[idx, date_col])
                quarterly_reports.append(report)
        
        return {
            "symbol": ticker,
            "annualReports": annual_reports,
            "quarterlyReports": quarterly_reports,
            "source": "yfinance_live",
        }
    except Exception as e:
        return {
            "symbol": ticker,
            "annualReports": [],
            "quarterlyReports": [],
            "error": f"yfinance fetch failed: {str(e)}",
        }


@cache_data(ttl_seconds=3600)
def get_cash_flow(ticker: str, as_of: str | None = None) -> dict[str, Any]:
    """
    Get cash flow statement for a ticker.
    
    HYBRID APPROACH:
    - If as_of is historical date → Use frozen Alpha Vantage data
    - If as_of is None/today → Use yfinance live
    
    Args:
        ticker: Stock ticker symbol
        as_of: ISO date string for point-in-time data
    
    Returns:
        Cash flow data with annualReports and quarterlyReports
    """
    if not _is_historical_date(as_of):
        return _get_yfinance_live_cashflow(ticker)
    
    data = _load_frozen_fundamentals(ticker, "cash_flow")
    
    if data is None:
        return {
            "symbol": ticker,
            "annualReports": [],
            "quarterlyReports": [],
            "error": "No cached fundamental data. Run freeze_fundamentals.py first.",
        }
    
    return {
        "symbol": data.get("symbol", ticker),
        "annualReports": _filter_by_date(data.get("annualReports", []), as_of),
        "quarterlyReports": _filter_by_date(data.get("quarterlyReports", []), as_of),
        "source": "alpha_vantage_frozen"
        "symbol": data.get("symbol", ticker),
        "annualReports": _filter_by_date(data.get("annualReports", []), as_of),
        "quarterlyReports": _filter_by_date(data.get("quarterlyReports", []), as_of),
    }


@cache_data(ttl_seconds=3600)
def get_cash_flow(ticker: str, as_of: str | None = None) -> dict[str, Any]:
    """
    Get cash flow statement for a ticker, filtered by as_of date.
    
    Returns both annual and quarterly reports, sorted by date descending.
    Only returns reports with fiscalDateEnding <= as_of.
    
    Args:
        ticker: Stock ticker symbol
        as_of: ISO date string for point-in-time data (e.g., '2021-11-15')
    
    Returns:
        {
            "symbol": str,
            "annualReports": list[dict],    # Filtered and sorted
            "quarterlyReports": list[dict],  # Filtered and sorted
        }
    """
    data = _load_frozen_fundamentals(ticker, "cash_flow")
    
    if data is None:
        return {
            "symbol": ticker,
            "annualReports": [],
            "quarterlyReports": [],
            "error": "No cached fundamental data. Run freeze_fundamentals.py first.",
        }
    
    return {
        "symbol": data.get("symbol", ticker),
        "annualReports": _filter_by_date(data.get("annualReports", []), as_of),
        "quarterlyReports": _filter_by_date(data.get("quarterlyReports", []), as_of),
    }


@cache_data(ttl_seconds=3600)
def get_financial_ratios(ticker: str, as_of: str | None = None) -> dict[str, Any]:
    """
    Calculate key financial ratios from the most recent statements as of the given date.
    
    Args:
        ticker: Stock ticker symbol
        as_of: ISO date string for point-in-time data
    
    Returns:
        Dictionary of calculated ratios
    """
    income = get_financial_statements(ticker, as_of)
    balance = get_balance_sheet(ticker, as_of)
    cash_flow = get_cash_flow(ticker, as_of)
    
    # Get most recent quarter for each
    latest_income = income.get("quarterlyReports", [{}])[0] if income.get("quarterlyReports") else {}
    latest_balance = balance.get("quarterlyReports", [{}])[0] if balance.get("quarterlyReports") else {}
    latest_cash = cash_flow.get("quarterlyReports", [{}])[0] if cash_flow.get("quarterlyReports") else {}
    
    def safe_float(value: str | None) -> float:
        """Convert string to float, return 0 if invalid."""
        try:
            return float(value) if value and value != "None" else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def safe_ratio(numerator: float, denominator: float) -> float:
        """Calculate ratio, return 0 if denominator is 0."""
        return numerator / denominator if denominator != 0 else 0.0
    
    # Extract values
    revenue = safe_float(latest_income.get("totalRevenue"))
    net_income = safe_float(latest_income.get("netIncome"))
    total_assets = safe_float(latest_balance.get("totalAssets"))
    total_equity = safe_float(latest_balance.get("totalShareholderEquity"))
    current_assets = safe_float(latest_balance.get("totalCurrentAssets"))
    current_liabilities = safe_float(latest_balance.get("totalCurrentLiabilities"))
    operating_cashflow = safe_float(latest_cash.get("operatingCashflow"))
    
    return {
        "fiscalDateEnding": latest_income.get("fiscalDateEnding"),
        "profitability": {
            "netProfitMargin": safe_ratio(net_income, revenue),
            "returnOnAssets": safe_ratio(net_income, total_assets),
            "returnOnEquity": safe_ratio(net_income, total_equity),
        },
        "liquidity": {
            "currentRatio": safe_ratio(current_assets, current_liabilities),
        },
        "cashflow": {
            "operatingCashflow": operating_cashflow,
            "freeCashflow": operating_cashflow,  # Simplified - would need capex
        },
        "rawValues": {
            "revenue": revenue,
            "netIncome": net_income,
            "totalAssets": total_assets,
            "totalEquity": total_equity,
        }
    }


def get_analyst_ratings(ticker: str, as_of: str | None = None) -> dict[str, Any]:
    """
    Placeholder for analyst ratings (not available from Alpha Vantage fundamentals).
    
    This would need a different data source or API endpoint.
    """
    return {
        "ticker": ticker,
        "as_of": as_of,
        "ratings": [],
        "error": "Analyst ratings not available in frozen fundamental data",
    }


def get_key_valuation_metrics(ticker: str, as_of: str | None = None) -> dict[str, Any]:
    """
    Extract key valuation metrics from fundamental statements.
    
    Args:
        ticker: Stock ticker symbol
        as_of: ISO date string for point-in-time data
    
    Returns:
        Dictionary of key metrics
    """
    income = get_financial_statements(ticker, as_of)
    balance = get_balance_sheet(ticker, as_of)
    
    latest_annual = income.get("annualReports", [{}])[0] if income.get("annualReports") else {}
    latest_balance = balance.get("annualReports", [{}])[0] if balance.get("annualReports") else {}
    
    def safe_float(value: str | None) -> float:
        try:
            return float(value) if value and value != "None" else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    return {
        "fiscalDateEnding": latest_annual.get("fiscalDateEnding"),
        "revenue": safe_float(latest_annual.get("totalRevenue")),
        "netIncome": safe_float(latest_annual.get("netIncome")),
        "ebitda": safe_float(latest_annual.get("ebitda")),
        "totalAssets": safe_float(latest_balance.get("totalAssets")),
        "totalLiabilities": safe_float(latest_balance.get("totalLiabilities")),
        "totalEquity": safe_float(latest_balance.get("totalShareholderEquity")),
        "bookValuePerShare": None,  # Would need shares outstanding
    }
