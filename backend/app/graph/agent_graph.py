# In nexustrader/backend/app/graph/agent_graph.py

from langgraph.graph import StateGraph, END
from .state import AgentState
from .conditional_logic import ConditionalLogic
from ..agents.analyst_team import (
    fundamental_analyst_agent,
    technical_analyst_agent,
    sentiment_analyst_agent,
    news_harvester_agent,
)
from ..agents.research_team import (
    bull_researcher_agent,
    bear_researcher_agent,
    research_manager_agent,
)
from ..agents.execution_core import (
    trading_strategy_synthesizer_agent,
    arbitrage_trader_agent,
    value_trader_agent,
    bull_trader_agent,
)
from ..agents.risk_management import (
    risk_management_agent,
    compliance_agent,
)

def create_agent_graph(max_debate_rounds: int = 3):
    """
    Creates the agent graph with conditional routing for debates.
    
    Args:
        max_debate_rounds: Maximum number of bull/bear debate rounds (default: 3)
    """
    # Create the conditional logic handler
    conditional_logic = ConditionalLogic(max_debate_rounds=max_debate_rounds)
    
    # Create the graph
    graph = StateGraph(AgentState)

    # ==================== ANALYST TEAM ====================
    # Add the nodes for the analyst team
    graph.add_node("fundamental_analyst", fundamental_analyst_agent)
    graph.add_node("technical_analyst", technical_analyst_agent)
    graph.add_node("sentiment_analyst", sentiment_analyst_agent)
    graph.add_node("news_harvester", news_harvester_agent)

    # ==================== RESEARCH TEAM ====================
    # Add the nodes for the research team (with debate capability)
    graph.add_node("bull_researcher", bull_researcher_agent)
    graph.add_node("bear_researcher", bear_researcher_agent)
    graph.add_node("research_manager", research_manager_agent)

    # ==================== EXECUTION CORE ====================
    # Add the nodes for the execution core
    graph.add_node("strategy_synthesizer", trading_strategy_synthesizer_agent)
    graph.add_node("arbitrage_trader", arbitrage_trader_agent)
    graph.add_node("value_trader", value_trader_agent)
    graph.add_node("bull_trader", bull_trader_agent)

    # ==================== RISK MANAGEMENT ====================
    # Add the nodes for the risk management team
    graph.add_node("risk_manager", risk_management_agent)
    graph.add_node("compliance_officer", compliance_agent)

    # ==================== GRAPH FLOW ====================
    
    # Set the entry point
    graph.set_entry_point("fundamental_analyst")

    # Analyst team - linear flow
    graph.add_edge("fundamental_analyst", "technical_analyst")
    graph.add_edge("technical_analyst", "sentiment_analyst")
    graph.add_edge("sentiment_analyst", "news_harvester")
    
    # Connect analyst team to research team - start with bull researcher
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
    
    # Research manager makes final decision and moves to execution
    graph.add_edge("research_manager", "strategy_synthesizer")
    
    # ==================== EXECUTION FLOW ====================
    # Execution core - linear flow through trader agents
    graph.add_edge("strategy_synthesizer", "arbitrage_trader")
    graph.add_edge("arbitrage_trader", "value_trader")
    graph.add_edge("value_trader", "bull_trader")

    # Connect execution core to risk management
    graph.add_edge("bull_trader", "risk_manager")
    graph.add_edge("risk_manager", "compliance_officer")

    # End the graph
    graph.add_edge("compliance_officer", END)

    # Compile the graph
    return graph.compile()
