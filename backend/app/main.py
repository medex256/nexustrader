# In nexustrader/backend/app/main.py

from .graph.agent_graph import create_agent_graph

def run_analysis():
    """
    Runs the agent graph for a given stock.
    """
    # Create the agent graph
    agent_graph = create_agent_graph()

    # Define the initial state
    initial_state = {
        "ticker": "NVDA",
        "market": "US",
        "reports": {},
        "stock_chart_image": None,
        "sentiment_score": 0.0,
        "arguments": {},
        "trading_strategy": {},
        "trader_reports": {},
        "risk_reports": {},
        "compliance_check": {},
        "proposed_trade": {},
    }

    # Invoke the graph
    print("Invoking the agent graph...")
    final_state = agent_graph.invoke(initial_state)

    # Print the final state
    print("\n--- Final State ---")
    print(final_state)

if __name__ == "__main__":
    run_analysis()
