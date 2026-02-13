# In nexustrader/backend/app/graph/agent_graph.py

from langgraph.graph import StateGraph, END
from .state import AgentState
from .conditional_logic import ConditionalLogic
from ..agents.analyst_team import (
    fundamental_analyst_agent,
    technical_analyst_agent,
    news_harvester_agent,
)
from ..agents.research_team import (
    bull_researcher_agent,
    bear_researcher_agent,
    research_manager_agent,
)
from ..agents.execution_core import (
    trading_strategy_synthesizer_agent,
)
from ..agents.risk_management import (
    risk_management_agent,
    aggressive_risk_analyst,
    conservative_risk_analyst,
    neutral_risk_analyst,
)

def create_agent_graph(max_debate_rounds: int = 1, max_risk_debate_rounds: int = 1):
    """
    Creates the agent graph with conditional routing for debates.
    
    Architecture (Feb 12, 2026 — aligned with TradingAgents paper):
    
    Layer 1 — Data Gathering (3 agents, 3 LLM calls):
      Fundamental Analyst → Technical Analyst → News Harvester
    
    Layer 2 — Investment Debate (3 agents, 3 LLM calls):
      Bull Researcher ↔ Bear Researcher → Research Manager (judge, deep thinking)
    
    Layer 3 — Trader (1 agent, 1 LLM call):
      Independent decision-maker. May DISAGREE with Research Manager.
    
    Layer 4 — Risk Debate (4 agents, 4-5 LLM calls):
      Aggressive ↔ Conservative ↔ Neutral → Risk Manager (judge, deep thinking)
      Evaluates tension between Research Manager and Trader decisions.
    
    Total: 11 agents, 11-12 LLM calls per run.
    Removed: Sentiment Analyst (dead placeholder — no social media APIs).
    
    Args:
        max_debate_rounds: Maximum number of bull/bear debate rounds (default: 1)
        max_risk_debate_rounds: Maximum number of risk debate rounds (default: 1)
    """
    # Create the conditional logic handler
    conditional_logic = ConditionalLogic(
        max_debate_rounds=max_debate_rounds,
        max_risk_rounds=max_risk_debate_rounds
    )
    
    # Create the graph
    graph = StateGraph(AgentState)

    # ==================== ANALYST TEAM (3 agents) ====================
    graph.add_node("fundamental_analyst", fundamental_analyst_agent)
    graph.add_node("technical_analyst", technical_analyst_agent)
    graph.add_node("news_harvester", news_harvester_agent)
    # NOTE: Sentiment Analyst removed — social media APIs unavailable.
    #       Was a dead placeholder returning hardcoded text.

    # ==================== RESEARCH TEAM (3 agents) ====================
    graph.add_node("bull_researcher", bull_researcher_agent)
    graph.add_node("bear_researcher", bear_researcher_agent)
    graph.add_node("research_manager", research_manager_agent)

    # ==================== TRADER (1 agent) ====================
    # Independent decision-maker — may disagree with Research Manager
    graph.add_node("strategy_synthesizer", trading_strategy_synthesizer_agent)

    # ==================== RISK MANAGEMENT (4 agents) ====================
    graph.add_node("aggressive_risk", aggressive_risk_analyst)
    graph.add_node("conservative_risk", conservative_risk_analyst)
    graph.add_node("neutral_risk", neutral_risk_analyst)
    graph.add_node("risk_manager", risk_management_agent)

    # ==================== GRAPH FLOW ====================
    
    # Set the entry point
    graph.set_entry_point("fundamental_analyst")

    # Analyst team — linear: Fundamental → Technical → News
    graph.add_edge("fundamental_analyst", "technical_analyst")
    graph.add_edge("technical_analyst", "news_harvester")
    
    # Connect analyst team to research team
    graph.add_edge("news_harvester", "bull_researcher")
    
    # ==================== DEBATE MECHANISM ====================
    # Bull researcher can go to bear researcher OR research manager
    graph.add_conditional_edges(
        "bull_researcher",
        conditional_logic.should_continue_debate,
        {
            "bear_researcher": "bear_researcher",
            "research_manager": "research_manager",
        }
    )
    
    # Bear researcher can go to bull researcher OR research manager
    graph.add_conditional_edges(
        "bear_researcher",
        conditional_logic.should_continue_debate,
        {
            "bull_researcher": "bull_researcher",
            "research_manager": "research_manager",
        }
    )
    
    # Research manager makes the investment decision, then strategy synthesizer creates the plan
    graph.add_edge("research_manager", "strategy_synthesizer")
    
    # ==================== RISK DEBATE MECHANISM ====================
    # Strategy synthesizer creates actionable plan, then starts risk debate
    graph.add_edge("strategy_synthesizer", "aggressive_risk")
    
    # Aggressive analyst can go to conservative OR risk manager (judge)
    graph.add_conditional_edges(
        "aggressive_risk",
        conditional_logic.should_continue_risk_debate,
        {
            "conservative_risk": "conservative_risk",
            "risk_manager": "risk_manager",
        }
    )
    
    # Conservative analyst can go to neutral OR risk manager
    graph.add_conditional_edges(
        "conservative_risk",
        conditional_logic.should_continue_risk_debate,
        {
            "neutral_risk": "neutral_risk",
            "risk_manager": "risk_manager",
        }
    )
    
    # Neutral analyst can loop back to aggressive OR go to risk manager
    graph.add_conditional_edges(
        "neutral_risk",
        conditional_logic.should_continue_risk_debate,
        {
            "aggressive_risk": "aggressive_risk",
            "risk_manager": "risk_manager",
        }
    )
    
    # ==================== END ====================
    # Risk manager makes final decision and ends the graph
    graph.add_edge("risk_manager", END)

    # Compile the graph
    return graph.compile()
