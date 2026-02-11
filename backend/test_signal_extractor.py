"""
Test the LLM-based signal extractor functionality.

This validates that extract_signal() can correctly identify BUY/SELL/HOLD
signals from various text formats, replacing fragile keyword matching.
"""

import sys
import os

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.agents.execution_core import extract_signal


def test_signal_extractor():
    """Test signal extractor with various input formats."""
    
    print("=" * 80)
    print("TESTING LLM-BASED SIGNAL EXTRACTOR")
    print("=" * 80)
    print()
    
    # Test cases: (text, expected_signal, description)
    test_cases = [
        # Explicit recommendations
        (
            "After thorough analysis, I recommend BUY for AAPL. The fundamentals are strong.",
            "BUY",
            "Explicit BUY recommendation"
        ),
        (
            "Given the bearish outlook, my recommendation is SELL. Exit positions now.",
            "SELL",
            "Explicit SELL recommendation"
        ),
        (
            "The situation is unclear. I recommend HOLD until more data is available.",
            "HOLD",
            "Explicit HOLD recommendation"
        ),
        
        # Synonyms and variations
        (
            "Strong momentum suggests accumulating shares at current levels. Go long.",
            "BUY",
            "BUY synonyms (accumulate, long)"
        ),
        (
            "Valuation too rich. Consider reducing exposure or exiting positions.",
            "SELL",
            "SELL synonyms (reduce, exit)"
        ),
        (
            "Market conditions warrant a wait-and-see approach. Stay neutral for now.",
            "HOLD",
            "HOLD synonyms (wait, neutral)"
        ),
        
        # Multi-paragraph with final recommendation
        (
            """The company has shown strong revenue growth in Q1 and Q2. 
            However, margin pressure from supply chain issues is concerning.
            Management guidance was mixed, with optimism on demand but caution on costs.
            
            That said, the technical setup looks favorable with support at $150.
            
            **Final Recommendation: BUY** - Scale in on dips below $155.""",
            "BUY",
            "Multi-paragraph with final BUY"
        ),
        
        # Embedded in JSON-like structure (but malformed)
        (
            """Here's my analysis:
            {
                "action": "SELL",
                "rationale": "Overvalued by 30% relative to peers"
                # Missing closing brace
            """,
            "SELL",
            "JSON-like but malformed (missing brace)"
        ),
        
        # Conversational style
        (
            "Alright team, after reviewing all the data, I think we should go long on this one. The risk/reward is attractive.",
            "BUY",
            "Conversational (go long)"
        ),
        
        # Ambiguous case (should default to HOLD)
        (
            "The stock could go either way. Depends on next earnings. Some analysts like it, others don't.",
            "HOLD",
            "Ambiguous (should default to HOLD)"
        ),
    ]
    
    results = []
    for i, (text, expected, description) in enumerate(test_cases, 1):
        print(f"Test {i}: {description}")
        print(f"Input text: {text[:100]}{'...' if len(text) > 100 else ''}")
        
        try:
            extracted = extract_signal(text, "AAPL")
            passed = extracted == expected
            results.append(passed)
            
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"Expected: {expected}")
            print(f"Extracted: {extracted}")
            print(f"Status: {status}")
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append(False)
        
        print("-" * 80)
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    pass_rate = passed / total * 100 if total > 0 else 0
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Passed: {passed}/{total} ({pass_rate:.1f}%)")
    print(f"Failed: {total - passed}/{total}")
    print()
    
    if pass_rate >= 80:
        print("✅ Signal extractor is working well!")
    else:
        print("⚠️  Signal extractor needs improvement")
    
    return pass_rate >= 80


if __name__ == "__main__":
    success = test_signal_extractor()
    sys.exit(0 if success else 1)
