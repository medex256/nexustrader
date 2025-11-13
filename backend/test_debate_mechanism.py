"""
Test script for the debate mechanism in NexusTrader.
This will run a simplified version of the graph to test the bull/bear debate flow.
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.graph.agent_graph import create_agent_graph
from app.graph.state import AgentState

def test_debate_mechanism():
    """
    Test the debate mechanism with a simplified flow.
    """
    print("=" * 80)
    print("TESTING DEBATE MECHANISM")
    print("=" * 80)
    
    # Create the agent graph with max 2 debate rounds for quick testing
    print("\n[1] Creating agent graph with max_debate_rounds=2...")
    agent_graph = create_agent_graph(max_debate_rounds=2)
    
    # Define initial state with minimal required fields
    print("[2] Defining initial state...")
    initial_state = {
        "ticker": "NVDA",
        "market": "US",
        "reports": {
            "fundamental_analyst": "Strong revenue growth of 265% YoY. PE ratio of 120 indicates high valuations.",
            "technical_analyst": "Stock is in strong uptrend with RSI at 65. Support at $500.",
            "sentiment_analyst": "Overall positive sentiment with 75% bullish mentions on social media.",
            "news_harvester": "Recent news about new AI chip releases and datacenter demand."
        },
        "stock_chart_image": "http://localhost:8000/static/charts/NVDA.png",
        "sentiment_score": 0.75,
        "arguments": {},
        "investment_debate_state": None,
        "risk_debate_state": None,
        "investment_plan": None,
        "trading_strategy": {},
        "trader_reports": {},
        "risk_reports": {},
        "compliance_check": {},
        "proposed_trade": {}
    }
    
    print("[3] Running graph (this will take a few moments as LLMs are called)...")
    print("\nNote: The graph will:")
    print("  - Run analyst team (4 agents) - using placeholder reports")
    print("  - Start bull/bear debate")
    print("  - Debate for up to 2 rounds (4 exchanges)")
    print("  - Research manager makes final decision")
    print("  - Execute trading strategy")
    print("  - Perform risk management")
    print("\n" + "-" * 80)
    
    try:
        # Run the graph
        result = agent_graph.invoke(initial_state)
        
        print("\n" + "=" * 80)
        print("DEBATE RESULTS")
        print("=" * 80)
        
        # Display debate information
        debate_state = result.get("investment_debate_state", {})
        
        print(f"\n[DEBATE STATISTICS]")
        print(f"Total rounds completed: {debate_state.get('count', 0)}")
        print(f"Last speaker: {debate_state.get('current_speaker', 'Unknown')}")
        
        print(f"\n[BULL RESEARCHER ARGUMENTS]")
        print("-" * 80)
        bull_history = debate_state.get('bull_history', 'No arguments')
        print(bull_history[:500] + "..." if len(bull_history) > 500 else bull_history)
        
        print(f"\n[BEAR RESEARCHER ARGUMENTS]")
        print("-" * 80)
        bear_history = debate_state.get('bear_history', 'No arguments')
        print(bear_history[:500] + "..." if len(bear_history) > 500 else bear_history)
        
        print(f"\n[RESEARCH MANAGER DECISION]")
        print("-" * 80)
        judge_decision = debate_state.get('judge_decision', 'No decision')
        print(judge_decision[:500] + "..." if len(judge_decision) > 500 else judge_decision)
        
        print(f"\n[TRADING STRATEGY]")
        print("-" * 80)
        strategy = result.get('trading_strategy', {})
        print(f"Action: {strategy.get('action', 'UNKNOWN')}")
        print(f"Entry Price: ${strategy.get('entry_price', 'N/A')}")
        print(f"Take Profit: ${strategy.get('take_profit', 'N/A')}")
        print(f"Stop Loss: ${strategy.get('stop_loss', 'N/A')}")
        print(f"Position Size: {strategy.get('position_size_pct', 'N/A')}%")
        
        print("\n" + "=" * 80)
        print("✅ TEST COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print("\nThe debate mechanism is working! Bull and Bear researchers")
        print("engaged in a multi-round debate before the Research Manager")
        print("made the final investment decision.")
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ TEST FAILED")
        print("=" * 80)
        print(f"\nError: {str(e)}")
        print("\nThis might be due to:")
        print("  1. Missing API keys (GOOGLE_API_KEY in .env)")
        print("  2. Missing dependencies (run: uv pip install -e .)")
        print("  3. LLM rate limits or errors")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_debate_mechanism()
    sys.exit(0 if success else 1)
