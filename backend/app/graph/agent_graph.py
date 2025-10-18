# In nexustrader/backend/app/graph/agent_graph.py

from langgraph.graph import StateGraph, END
from .state import AgentState
from ..agents.analyst_team import (
    fundamental_analyst_agent,
    technical_analyst_agent,
    sentiment_analyst_agent,
    news_harvester_agent,
)
from ..agents.research_team import (
    bull_researcher_agent,
    bear_researcher_agent,
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

def create_agent_graph():
    """
    Creates the agent graph.
    """
    # Create the graph
    graph = StateGraph(AgentState)

    # Add the nodes for the analyst team
    graph.add_node("fundamental_analyst", fundamental_analyst_agent)
    graph.add_node("technical_analyst", technical_analyst_agent)
    graph.add_node("sentiment_analyst", sentiment_analyst_agent)
    graph.add_node("news_harvester", news_harvester_agent)

    # Add the nodes for the research team
    graph.add_node("bull_researcher", bull_researcher_agent)
    graph.add_node("bear_researcher", bear_researcher_agent)

    # Add the nodes for the execution core
    graph.add_node("strategy_synthesizer", trading_strategy_synthesizer_agent)
    graph.add_node("arbitrage_trader", arbitrage_trader_agent)
    graph.add_node("value_trader", value_trader_agent)
    graph.add_node("bull_trader", bull_trader_agent)

    # Add the nodes for the risk management team
    graph.add_node("risk_manager", risk_management_agent)
    graph.add_node("compliance_officer", compliance_agent)

    # Set the entry point
    graph.set_entry_point("fundamental_analyst")

    # Define the edges for the analyst team
    graph.add_edge("fundamental_analyst", "technical_analyst")
    graph.add_edge("technical_analyst", "sentiment_analyst")
    graph.add_edge("sentiment_analyst", "news_harvester")
    
    # Connect the analyst team to the research team
    graph.add_edge("news_harvester", "bull_researcher")
    
    # Define the edges for the research team
    graph.add_edge("bull_researcher", "bear_researcher")

    # Connect the research team to the execution core
    graph.add_edge("bear_researcher", "strategy_synthesizer")
    graph.add_edge("strategy_synthesizer", "arbitrage_trader")
    graph.add_edge("arbitrage_trader", "value_trader")
    graph.add_edge("value_trader", "bull_trader")

    # Connect the execution core to the risk management team
    graph.add_edge("bull_trader", "risk_manager")
    graph.add_edge("risk_manager", "compliance_officer")

    # End the graph
    graph.add_edge("compliance_officer", END)

    # Compile the graph
    return graph.compile()