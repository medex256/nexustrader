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

def create_agent_graph(
    max_debate_rounds: int = 1,
    max_risk_debate_rounds: int = 1,
    risk_mode: str = "single",
    debate_mode: str = "on",
):
    """
    Creates the agent graph with conditional routing for debates.
    
        Architecture (Mar 8, 2026):
    
    Layer 1 — Data Gathering (3 agents, 3 LLM calls):
      Fundamental Analyst → Technical Analyst → News Harvester
    
        Layer 2 — Research refinement:
            - Stage B / B+: Upside Catalyst Analyst → Downside Risk Analyst → Research Manager
            - Stage C / D: Bull Researcher ↔ Bear Researcher → Research Manager
    
        Layer 3 — Trader:
            - Stage A / B / B+: policy core (no LLM call)
            - Stage C / D: independent Trader may DISAGREE with Research Manager
    
        Layer 4 — Risk Mode (configurable):
            - off: skip risk layer
            - single: Risk Manager (single risk-check judge)
            - debate: Aggressive ↔ Conservative ↔ Neutral → Risk Manager
    
        Total active path:
                        - Stage A: 4 LLM calls
                        - Stage B: 6 LLM calls
                        - Stage B+: 7 LLM calls
                        - Stage C/D: 11+ LLM calls
    Removed: Sentiment Analyst (dead placeholder — no social media APIs).
    
    Args:
        max_debate_rounds: Maximum number of bull/bear debate rounds when full debate is active (default: 1)
        max_risk_debate_rounds: Maximum number of risk debate rounds (default: 1)
        risk_mode: "off" | "single" | "debate"
        debate_mode: "on" | "off"
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

    # ==================== RESEARCH TEAM ====================
    # Keep both research nodes registered.
    # Stage B / B+ route through them as two non-adversarial specialist extractors.
    # Stage C / D use both nodes for the full bull/bear debate.
    graph.add_node("bull_researcher", bull_researcher_agent)
    graph.add_node("bear_researcher", bear_researcher_agent)
    graph.add_node("research_manager", research_manager_agent)

    # ==================== TRADER (1 agent) ====================
    # Independent decision-maker — may disagree with Research Manager
    graph.add_node("strategy_synthesizer", trading_strategy_synthesizer_agent)

    # ==================== RISK MANAGEMENT ====================
    # Keep legacy debate nodes registered for compatibility, but route bypasses them.
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
    debate_mode_normalized = (debate_mode or "on").strip().lower()
    debate_enabled = debate_mode_normalized != "off" and max_debate_rounds > 0
    risk_mode_normalized = (risk_mode or "single").strip().lower()
    single_extraction_mode = debate_enabled and risk_mode_normalized in {"off", "single"}

    if debate_enabled:
        graph.add_edge("news_harvester", "bull_researcher")
    else:
        graph.add_edge("news_harvester", "research_manager")
    
    # ==================== RESEARCH ROUTING ====================
    if single_extraction_mode:
        graph.add_edge("bull_researcher", "bear_researcher")
        graph.add_edge("bear_researcher", "research_manager")
    elif debate_enabled:
        graph.add_conditional_edges(
            "bull_researcher",
            conditional_logic.should_continue_debate,
            {
                "bear_researcher": "bear_researcher",
                "research_manager": "research_manager",
            }
        )

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
    
    # ==================== RISK MODE ROUTING ====================
    if risk_mode_normalized == "off":
        graph.add_edge("strategy_synthesizer", END)
    elif risk_mode_normalized == "debate":
        graph.add_edge("strategy_synthesizer", "aggressive_risk")

        graph.add_conditional_edges(
            "aggressive_risk",
            conditional_logic.should_continue_risk_debate,
            {
                "conservative_risk": "conservative_risk",
                "risk_manager": "risk_manager",
            }
        )

        graph.add_conditional_edges(
            "conservative_risk",
            conditional_logic.should_continue_risk_debate,
            {
                "neutral_risk": "neutral_risk",
                "risk_manager": "risk_manager",
            }
        )

        graph.add_conditional_edges(
            "neutral_risk",
            conditional_logic.should_continue_risk_debate,
            {
                "aggressive_risk": "aggressive_risk",
                "risk_manager": "risk_manager",
            }
        )
    else:
        graph.add_edge("strategy_synthesizer", "risk_manager")
    
    # ==================== END ====================
    # Risk manager makes final decision when risk stage is active
    graph.add_edge("risk_manager", END)

    # Compile the graph
    return graph.compile()
