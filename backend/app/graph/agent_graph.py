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
    aggressive_risk_analyst,
    conservative_risk_analyst,
    neutral_risk_analyst,
)

def create_agent_graph(max_debate_rounds: int = 1, max_risk_debate_rounds: int = 1):
    """
    Creates the agent graph with conditional routing for debates.
    
    Architecture (Feb 11, 2026 update):
    - 4 Analysts: Fundamental, Technical, Sentiment, News
    - 3 Investment Debate: Bull Researcher, Bear Researcher, Research Manager
    - 1 Strategy: Trading Strategy Synthesizer
    - 3 Risk Debate: Aggressive, Conservative, Neutral Risk Analysts
    - 1 Risk Judge: Risk Manager (evaluates debate)
    
    Total: 12 agents (was 9 before risk debate addition)
    
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
    # Strategy synthesizer (converts research plan to actionable trade)
    graph.add_node("strategy_synthesizer", trading_strategy_synthesizer_agent)

    # ==================== RISK MANAGEMENT ====================
    # Risk debate analysts (3 perspectives)
    graph.add_node("aggressive_risk", aggressive_risk_analyst)
    graph.add_node("conservative_risk", conservative_risk_analyst)
    graph.add_node("neutral_risk", neutral_risk_analyst)
    # Risk manager (final judge)
    graph.add_node("risk_manager", risk_management_agent)

    # ==================== GRAPH FLOW ====================
    
    # Set the entry point
    graph.set_entry_point("fundamental_analyst")

    # Analyst team - linear flow
    graph.add_edge("fundamental_analyst", "technical_analyst")

    # Conditionally include social sentiment
    graph.add_conditional_edges(
        "technical_analyst",
        conditional_logic.should_include_social,
        {
            "sentiment_analyst": "sentiment_analyst",
            "news_harvester": "news_harvester",
        }
    )

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
