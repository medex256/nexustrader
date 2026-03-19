# In nexustrader/backend/app/graph/conditional_logic.py

from .state import AgentState


class ConditionalLogic:
    """
    Handles active conditional routing logic for debate and risk debate.
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
        - If the upside / bull-side researcher just spoke -> go to Bear
        - If the downside / bear-side researcher just spoke -> go to Bull
        
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
        current_speaker = (debate_state.get("current_speaker", "") or "").strip()

        # Stage B / B+ renamed the first-layer researchers from Bull/Bear advocates
        # to specialist extractors. Keep routing compatible with both label schemes.
        bull_side_speakers = {"Bull Researcher", "Upside Catalyst Analyst"}
        bear_side_speakers = {"Bear Researcher", "Downside Risk Analyst"}

        if current_speaker.startswith("Bull") or current_speaker in bull_side_speakers:
            return "bear_researcher"
        if current_speaker.startswith("Bear") or current_speaker in bear_side_speakers:
            return "bull_researcher"

        # Default to bull if speaker is missing / unknown.
        return "bull_researcher"

    def should_continue_risk_debate(self, state: AgentState) -> str:
        """
        Determine if the risk debate should continue or move to Risk Manager (judge).
        
        Logic:
        - If max rounds reached (count >= 3 * max_risk_rounds) -> go to Risk Manager
        - Route in order: Aggressive -> Conservative -> Neutral -> (loop or end)
        - Each complete cycle = 3 exchanges (one per analyst)
        
        Args:
            state: Current agent state with risk debate information
            
        Returns:
            Next node name: "conservative_risk", "neutral_risk", "aggressive_risk", or "risk_manager"
        """
        risk_state = state.get("risk_debate_state", {})
        
        # Check if we've reached max rounds (each round = 3 exchanges)
        if risk_state.get("count", 0) >= 3 * self.max_risk_rounds:
            return "risk_manager"
        
        # Determine next speaker in rotation
        latest_speaker = risk_state.get("latest_speaker", "")
        
        if latest_speaker == "Aggressive":
            return "conservative_risk"
        elif latest_speaker == "Conservative":
            return "neutral_risk"
        elif latest_speaker == "Neutral":
            # After neutral, check if we should continue or end
            if risk_state.get("count", 0) >= 3 * self.max_risk_rounds - 1:
                # This was the last exchange, go to judge
                return "risk_manager"
            else:
                # Continue for another round
                return "aggressive_risk"
        else:
            # Default to aggressive (start of debate)
            return "conservative_risk"  # Should go to conservative after aggressive's first turn

    def should_include_social(self, state: AgentState) -> str:
        """
        Legacy helper retained for optional social/sentiment experiments.
        Not used by the current frozen A/B/B+/C/D stage graph.

        Returns:
            Next node name: "sentiment_analyst" or "news_harvester"
        """
        run_config = state.get("run_config", {})
        if run_config.get("social_on", False):
            return "sentiment_analyst"
        return "news_harvester"
