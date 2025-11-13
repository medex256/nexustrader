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
    # Removed redundant traders: arbitrage, value, bull
    # These duplicated work done by analysts and researchers
)
from ..agents.risk_management import (
    risk_management_agent,
    # Removed compliance_agent - Risk Manager handles this for MVP
)

def create_agent_graph(max_debate_rounds: int = 1):
    """
    Creates the agent graph with conditional routing for debates.
    
    Streamlined 9-agent architecture:
    - 4 Analysts: Fundamental, Technical, Sentiment, News
    - 3 Debate: Bull Researcher, Bear Researcher, Research Manager
    - 1 Strategy: Trading Strategy Synthesizer
    - 1 Risk: Risk Management Agent
    
    Removed redundant agents (arbitrage, value, bull traders) that 
    duplicated work done by analysts and researchers.
    
    Args:
        max_debate_rounds: Maximum number of bull/bear debate rounds (default: 1)
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
    # Add the node for strategy synthesis (converts research to actionable plan)
    graph.add_node("strategy_synthesizer", trading_strategy_synthesizer_agent)

    # ==================== RISK MANAGEMENT ====================
    # Add the node for risk management (final safety check)
    graph.add_node("risk_manager", risk_management_agent)

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
    # Strategy synthesizer creates actionable plan, then risk check
    graph.add_edge("strategy_synthesizer", "risk_manager")

    # End the graph after risk management
    graph.add_edge("risk_manager", END)

    # Compile the graph
    return graph.compile()
