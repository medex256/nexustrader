# In nexustrader/backend/app/graph/state.py

from typing import TypedDict, Dict, Any, List, Optional

class InvestDebateState(TypedDict):
    """
    State for tracking the bull vs bear investment debate.
    """
    history: str  # Full debate transcript
    bull_history: str  # Bull-specific arguments
    bear_history: str  # Bear-specific arguments
    current_response: str  # Last speaker's response
    current_speaker: str  # Who spoke last (Bull/Bear)
    count: int  # Number of debate rounds completed
    judge_decision: str  # Final decision from research manager

class RiskDebateState(TypedDict):
    """
    State for tracking the risk management debate.
    """
    history: str  # Full risk debate transcript
    latest_speaker: str  # Last speaker (Risky/Safe/Neutral)
    count: int  # Number of risk rounds completed
    final_decision: str  # Final risk assessment

class RunConfig(TypedDict, total=False):
    """Runtime configuration flags for ablations and evaluation modes."""
    simulated_date: Optional[str]
    horizon: str  # "short"|"medium"|"long"
    horizon_days: int  # 10|21|126
    debate_rounds: int  # 0|1|2
    memory_on: bool
    risk_on: bool
    social_on: bool

class AgentState(TypedDict):
    """
    The state of the agent graph.
    """
    ticker: str
    market: str
    run_config: RunConfig
    simulated_date: Optional[str]
    horizon: str  # "short"|"medium"|"long"
    horizon_days: int  # 10|21|126
    reports: Dict[str, str]
    stock_chart_image: Any  # This could be a path to an image or image data
    sentiment_score: float
    
    # Debate states
    investment_debate_state: Optional[InvestDebateState]
    risk_debate_state: Optional[RiskDebateState]
    
    # Research outputs
    arguments: Dict[str, str]
    investment_plan: Optional[str]  # From research manager
    
    # Execution outputs
    trading_strategy: Dict[str, Any]
    trader_reports: Dict[str, str]
    
    # Risk management outputs
    risk_reports: Dict[str, str]
    compliance_check: Dict[str, Any]
    proposed_trade: Dict[str, Any]
    
    # Debug/Verification metadata
    provenance: Optional[Dict[str, Any]]  # News timestamps, chart as-of, etc.
