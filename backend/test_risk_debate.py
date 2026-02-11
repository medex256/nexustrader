# Test script for risk debate mechanism
# Run from nexustrader/backend directory

import sys
import json
from app.graph.agent_graph import create_agent_graph

def test_risk_debate(ticker="AAPL", date="2024-03-01"):
    """
    Test the risk debate mechanism on a single ticker.
    This will help verify HOLD rate drops and debate works correctly.
    """
    print(f"\n{'='*80}")
    print(f"Testing Risk Debate for {ticker} on {date}")
    print(f"{'='*80}\n")
    
    # Create graph with risk debate enabled (1 round = 3 exchanges)
    graph = create_agent_graph(
        max_debate_rounds=1,  # Bull/Bear debate
        max_risk_debate_rounds=1  # Risk debate (aggressive/conservative/neutral)
    )
    
    # Initialize state
    initial_state = {
        "ticker": ticker,
        "market": "US",
        "simulated_date": date,
        "horizon": "short",
        "horizon_days": 10,
        "run_config": {
            "simulated_date": date,
            "horizon": "short",
            "horizon_days": 10,
            "debate_rounds": 1,
            "memory_on": False,
            "risk_on": True,
            "social_on": False,
        },
        "reports": {},
        "sentiment_score": 0.0,
        "investment_debate_state": None,
        "risk_debate_state": None,
        "arguments": {},
        "investment_plan": None,
        "trading_strategy": {},
        "trader_reports": {},
        "risk_reports": {},
        "compliance_check": {},
        "proposed_trade": {},
        "provenance": None,
    }
    
    print("Running graph...")
    print(f"Graph will execute: Analysts → Bull/Bear Debate → Strategy → Risk Debate → Final Decision\n")
    
    try:
        # Run the graph
        result = graph.invoke(initial_state)
        
        # Extract key results
        final_strategy = result.get("trading_strategy", {})
        action = final_strategy.get("action", "UNKNOWN")
        risk_debate_state = result.get("risk_debate_state", {})
        risk_report = result.get("risk_reports", {})
        
        print(f"\n{'='*80}")
        print("RESULTS")
        print(f"{'='*80}\n")
        
        print(f"Final Decision: {action}")
        print(f"Position Size: {final_strategy.get('position_size_pct', 0)}%")
        print(f"Entry Price: ${final_strategy.get('entry_price', 'N/A')}")
        print(f"Stop Loss: ${final_strategy.get('stop_loss', 'N/A')}")
        print(f"Take Profit: ${final_strategy.get('take_profit', 'N/A')}")
        print(f"\nRationale: {final_strategy.get('rationale', 'N/A')[:200]}...")
        
        print(f"\n{'='*80}")
        print("RISK DEBATE SUMMARY")
        print(f"{'='*80}\n")
        
        if risk_debate_state:
            print(f"Total Exchanges: {risk_debate_state.get('count', 0)}")
            print(f"Last Speaker: {risk_debate_state.get('latest_speaker', 'N/A')}")
            
            # Show abbreviated arguments
            agg_hist = risk_debate_state.get('aggressive_history', '')
            cons_hist = risk_debate_state.get('conservative_history', '')
            neut_hist = risk_debate_state.get('neutral_history', '')
            
            if agg_hist:
                print(f"\nAggressive Analyst (excerpt):")
                print(f"{agg_hist[:300]}...\n")
            
            if cons_hist:
                print(f"Conservative Analyst (excerpt):")
                print(f"{cons_hist[:300]}...\n")
            
            if neut_hist:
                print(f"Neutral Analyst (excerpt):")
                print(f"{neut_hist[:300]}...\n")
            
            print(f"\nRisk Manager Decision:")
            mgr_decision = risk_report.get('risk_manager_decision', 'N/A')
            print(f"{mgr_decision[:400]}...")
        else:
            print("No risk debate occurred (debate might be disabled)")
        
        print(f"\n{'='*80}")
        print(f"Test completed for {ticker}")
        print(f"{'='*80}\n")
        
        # Return action for batch testing
        return action
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return "ERROR"


if __name__ == "__main__":
    # Test on a few tickers
    test_tickers = [
        ("AAPL", "2024-03-01"),
        ("TSLA", "2024-03-01"),
        ("NVDA", "2024-03-01"),
    ]
    
    results = {}
    for ticker, date in test_tickers:
        action = test_risk_debate(ticker, date)
        results[ticker] = action
        print("\n" + "="*80 + "\n")
    
    # Summary
    print("\n" + "="*80)
    print("BATCH TEST SUMMARY")
    print("="*80 + "\n")
    
    hold_count = sum(1 for a in results.values() if a == "HOLD")
    buy_count = sum(1 for a in results.values() if a == "BUY")
    sell_count = sum(1 for a in results.values() if a == "SELL")
    error_count = sum(1 for a in results.values() if a == "ERROR")
    
    total = len(results)
    
    print(f"Total Runs: {total}")
    print(f"BUY: {buy_count} ({buy_count/total*100:.1f}%)")
    print(f"SELL: {sell_count} ({sell_count/total*100:.1f}%)")
    print(f"HOLD: {hold_count} ({hold_count/total*100:.1f}%)")
    print(f"ERRORS: {error_count}")
    
    print(f"\nTarget: HOLD rate should be <50% (was 75.5% before risk debate)")
    print(f"Actual: {hold_count/total*100:.1f}%")
    
    if hold_count/total < 0.5:
        print("\n✅ SUCCESS: HOLD rate is below 50%!")
    else:
        print("\n⚠️  HOLD rate still high - may need prompt tuning")
    
    print("\nDetailed Results:")
    for ticker, action in results.items():
        print(f"  {ticker}: {action}")
