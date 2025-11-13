# In nexustrader/backend/app/graph/conditional_logic.py

from .state import AgentState


class ConditionalLogic:
    """
    Handles conditional routing logic for the agent graph.
    Determines which agent should execute next based on current state.
    """

    def __init__(self, max_debate_rounds: int = 3, max_risk_rounds: int = 2):
        """
        Initialize conditional logic with configuration.
        
        Args:
            max_debate_rounds: Maximum number of bull/bear debate rounds
            max_risk_rounds: Maximum number of risk debate rounds
        """
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_rounds = max_risk_rounds

    def should_continue_debate(self, state: AgentState) -> str:
        """
        Determine if the investment debate should continue or move to research manager.
        
        Logic:
        - If max rounds reached -> go to Research Manager
        - If Bull just spoke -> go to Bear
        - If Bear just spoke -> go to Bull
        
        Args:
            state: Current agent state with debate information
            
        Returns:
            Next node name: "bull_researcher", "bear_researcher", or "research_manager"
        """
        debate_state = state.get("investment_debate_state", {})
        
        # Check if we've reached max rounds (each round = 2 exchanges)
        if debate_state.get("count", 0) >= 2 * self.max_debate_rounds:
            return "research_manager"
        
        # Determine next speaker based on current speaker
        current_speaker = debate_state.get("current_speaker", "")
        
        if current_speaker.startswith("Bull"):
            return "bear_researcher"
        else:
            # Default to bull if no speaker or bear just spoke
            return "bull_researcher"

    def should_continue_risk_debate(self, state: AgentState) -> str:
        """
        Determine if the risk debate should continue or move to final risk assessment.
        
        Logic:
        - If max rounds reached -> go to Risk Manager (final decision)
        - Route through: Aggressive -> Conservative -> Neutral -> repeat
        
        Args:
            state: Current agent state with risk debate information
            
        Returns:
            Next node name for risk management flow
        """
        risk_state = state.get("risk_debate_state", {})
        
        # Check if we've reached max rounds
        if risk_state.get("count", 0) >= 3 * self.max_risk_rounds:
            return "risk_manager_final"
        
        # Determine next speaker in rotation
        latest_speaker = risk_state.get("latest_speaker", "")
        
        if latest_speaker.startswith("Aggressive"):
            return "conservative_risk"
        elif latest_speaker.startswith("Conservative"):
            return "neutral_risk"
        else:
            # Default to aggressive or start of cycle
            return "aggressive_risk"

    def should_execute_strategy(self, state: AgentState) -> str:
        """
        Determine which execution strategy to use based on the investment plan.
        
        Args:
            state: Current agent state
            
        Returns:
            Next execution node
        """
        investment_plan = state.get("investment_plan", "")
        
        # Simple routing based on recommendation keywords
        if "buy" in investment_plan.lower() or "bullish" in investment_plan.lower():
            return "strategy_synthesizer"
        elif "sell" in investment_plan.lower() or "bearish" in investment_plan.lower():
            return "strategy_synthesizer"
        else:
            # HOLD scenario - might skip execution
            return "strategy_synthesizer"

    def should_skip_compliance(self, state: AgentState) -> str:
        """
        Determine if compliance check is needed based on strategy.
        
        Args:
            state: Current agent state
            
        Returns:
            Next node: "compliance_officer" or "END"
        """
        strategy = state.get("trading_strategy", {})
        action = strategy.get("action", "HOLD")
        
        # Only check compliance for BUY/SELL actions
        if action in ["BUY", "SELL"]:
            return "compliance_officer"
        else:
            # HOLD doesn't need compliance
            return "END"
