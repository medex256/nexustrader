"""
Quick comparison: NexusTrader vs Baselines

Runs a single ticker through all strategies (agentic + non-agentic) for side-by-side comparison.

Usage:
    python scripts/quick_compare.py AAPL 2024-12-31
"""

import sys
import json
import requests
from datetime import datetime


def run_nexustrader(ticker: str, simulated_date: str, backend_url: str = "http://localhost:8000"):
    """Run NexusTrader analysis."""
    print(f"\n{'='*80}")
    print(f"NEXUSTRADER (Agentic)")
    print('='*80)
    
    url = f"{backend_url}/analyze"
    payload = {
        "ticker": ticker,
        "simulated_date": simulated_date,
        "horizon": "short",
        "debate_rounds": 1,
        "memory_on": False,
        "risk_on": True,
        "social_on": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        result = response.json()
        
        ts = result.get('trading_strategy', {})
        print(f"Action: {ts.get('action', 'N/A')}")
        print(f"Entry: {ts.get('entry_price', 'N/A')}")
        print(f"Take Profit: {ts.get('take_profit', 'N/A')}")
        print(f"Stop Loss: {ts.get('stop_loss', 'N/A')}")
        print(f"Position %: {ts.get('position_size_pct', 'N/A')}")
        print(f"Rationale: {ts.get('rationale', 'N/A')[:150]}...")
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None


def run_baseline(ticker: str, simulated_date: str, baseline_name: str, backend_url: str = "http://localhost:8000"):
    """Run a baseline strategy."""
    print(f"\n{'='*80}")
    print(f"{baseline_name.upper().replace('_', ' ')} (Baseline)")
    print('='*80)
    
    url = f"{backend_url}/baseline"
    payload = {
        "ticker": ticker,
        "baseline": baseline_name,
        "simulated_date": simulated_date
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        ts = result.get('trading_strategy', {})
        print(f"Action: {ts.get('action', 'N/A')}")
        print(f"Entry: {ts.get('entry_price', 'N/A')}")
        print(f"Take Profit: {ts.get('take_profit', 'N/A')}")
        print(f"Stop Loss: {ts.get('stop_loss', 'N/A')}")
        print(f"Position %: {ts.get('position_size_pct', 'N/A')}")
        print(f"Rationale: {ts.get('rationale', 'N/A')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/quick_compare.py TICKER SIMULATED_DATE")
        print("Example: python scripts/quick_compare.py AAPL 2024-12-31")
        sys.exit(1)
    
    ticker = sys.argv[1].upper()
    simulated_date = sys.argv[2]
    
    print(f"\n🔬 Quick Comparison: {ticker} as of {simulated_date}")
    print(f"{'='*80}\n")
    
    results = {}
    
    # Run NexusTrader (agentic)
    results['nexustrader'] = run_nexustrader(ticker, simulated_date)
    
    # Run all baselines
    for baseline in ['buy_hold', 'sma', 'rsi', 'random']:
        results[baseline] = run_baseline(ticker, simulated_date, baseline)
    
    # Summary table
    print(f"\n{'='*80}")
    print("SUMMARY TABLE")
    print('='*80)
    print(f"{'Strategy':<20} {'Action':<8} {'Entry':<10} {'Position %':<12}")
    print('-'*80)
    
    for name, result in results.items():
        if result:
            ts = result.get('trading_strategy', {})
            action = ts.get('action', 'N/A')
            entry = ts.get('entry_price', 'N/A')
            if entry != 'N/A' and entry is not None:
                entry = f"${entry:.2f}"
            position = ts.get('position_size_pct', 'N/A')
            if position != 'N/A' and position is not None:
                position = f"{position}%"
            
            display_name = name.replace('_', ' ').title()
            print(f"{display_name:<20} {action:<8} {entry:<10} {position:<12}")
    
    print('='*80)
    print("\n✅ Comparison complete\n")
    
    # Save to file
    output_file = f"results/quick_compare_{ticker}_{simulated_date.replace('-', '')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"💾 Results saved to: {output_file}\n")


if __name__ == "__main__":
    main()
