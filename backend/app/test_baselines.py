"""
Test script for non-agentic baseline strategies.

Usage:
    python -m app.test_baselines
"""

from app.baselines.strategies import get_baseline


def test_all_baselines():
    """Test all baseline strategies with a sample ticker."""
    
    ticker = "AAPL"
    simulated_date = "2024-12-31"
    
    baselines = ['buy_hold', 'sma', 'rsi', 'random']
    
    print(f"Testing baselines for {ticker} as of {simulated_date}\n")
    print("=" * 80)
    
    for baseline_name in baselines:
        print(f"\n[{baseline_name.upper()}]")
        print("-" * 80)
        
        try:
            strategy = get_baseline(baseline_name)
            result = strategy.generate_signal(ticker, simulated_date)
            
            ts = result['trading_strategy']
            print(f"Action: {ts['action']}")
            print(f"Entry: {ts['entry_price']}")
            print(f"Take Profit: {ts['take_profit']}")
            print(f"Stop Loss: {ts['stop_loss']}")
            print(f"Position %: {ts['position_size_pct']}")
            print(f"Rationale: {ts['rationale']}")
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
    
    print("\n" + "=" * 80)
    print("✅ All baselines tested successfully")


if __name__ == "__main__":
    test_all_baselines()
