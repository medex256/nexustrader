# In nexustrader/backend/app/graph/state.py

from typing import TypedDict, Dict, Any, List

class AgentState(TypedDict):
    """
    The state of the agent graph.
    """
    ticker: str
    market: str
    reports: Dict[str, str]
    stock_chart_image: Any  # This could be a path to an image or image data
    sentiment_score: float
    arguments: Dict[str, str]
    trading_strategy: Dict[str, Any]
    trader_reports: Dict[str, str]
    risk_reports: Dict[str, str]
    compliance_check: Dict[str, Any]
    proposed_trade: Dict[str, Any]
