# In nexustrader/backend/app/graph/agent_graph.py

from langgraph.graph import StatefulGraph, END
from .state import AgentState
from ..agents.analyst_team import (
    fundamental_analyst_agent,
    technical_analyst_agent,
    sentiment_analyst_agent,
    news_harvester_agent,
)
# We will import the other agents later

def create_agent_graph():
    """
    Creates the agent graph.
    """
    # Create the graph
    graph = StatefulGraph(AgentState)

    # Add the nodes for the analyst team
    graph.add_node("fundamental_analyst", fundamental_analyst_agent)
    graph.add_node("technical_analyst", technical_analyst_agent)
    graph.add_node("sentiment_analyst", sentiment_analyst_agent)
    graph.add_node("news_harvester", news_harvester_agent)

    # Set the entry point
    graph.set_entry_point("fundamental_analyst")

    # Define the edges for the analyst team
    graph.add_edge("fundamental_analyst", "technical_analyst")
    graph.add_edge("technical_analyst", "sentiment_analyst")
    graph.add_edge("sentiment_analyst", "news_harvester")
    
    # We will add the rest of the graph later
    graph.add_edge("news_harvester", END) # For now, end after the analyst team

    # Compile the graph
    return graph.compile()
