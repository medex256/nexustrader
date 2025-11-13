#!/usr/bin/env python3
"""
Test script for the Memory System
Tests memory storage and retrieval without requiring LLM calls.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.utils.memory import FinancialMemory


def test_memory_system():
    """Test the financial memory system."""
    
    print("="*80)
    print("TESTING FINANCIAL MEMORY SYSTEM")
    print("="*80)
    print()
    
    # Initialize memory
    print("[1] Initializing memory system...")
    memory = FinancialMemory(persist_directory="./test_chroma_db", collection_name="test_memory")
    print()
    
    # Store some example analyses
    print("[2] Storing example analyses...")
    
    # Example 1: Successful NVDA analysis
    memory_id_1 = memory.store_analysis(
        ticker="NVDA",
        analysis_summary="NVIDIA showing strong AI-driven growth but extreme valuation concerns",
        bull_arguments="""
        - 80%+ market share in AI chips
        - 265% YoY revenue growth
        - Unprecedented pricing power
        - Multi-year AI supercycle ahead
        """,
        bear_arguments="""
        - 120x P/E ratio is excessive
        - Increased competition from AMD
        - Insider selling signals
        - Market saturation risks
        """,
        final_decision="SELL - Valuation too extreme despite strong fundamentals",
        strategy={
            "action": "SELL",
            "entry_price": 900,
            "take_profit": 675,
            "stop_loss": 990,
            "position_size_pct": 7
        },
        metadata={"market_condition": "Bull market", "sector": "Technology"}
    )
    print(f"   Stored: {memory_id_1}")
    
    # Example 2: TSLA analysis
    memory_id_2 = memory.store_analysis(
        ticker="TSLA",
        analysis_summary="Tesla showing momentum with delivery numbers beating expectations",
        bull_arguments="""
        - Strong delivery growth
        - FSD improving rapidly
        - Energy division growing
        - Musk back focused on Tesla
        """,
        bear_arguments="""
        - Competition intensifying
        - Margins compressing
        - High valuation vs auto peers
        - Execution risks
        """,
        final_decision="BUY - Momentum and delivery numbers strong",
        strategy={
            "action": "BUY",
            "entry_price": 235,
            "take_profit": 275,
            "stop_loss": 220,
            "position_size_pct": 5
        },
        metadata={"market_condition": "Bull market", "sector": "Automotive"}
    )
    print(f"   Stored: {memory_id_2}")
    
    # Example 3: AAPL analysis
    memory_id_3 = memory.store_analysis(
        ticker="AAPL",
        analysis_summary="Apple showing steady performance but limited upside catalysts",
        bull_arguments="""
        - Strong services revenue
        - Loyal customer base
        - Apple Intelligence coming
        - Strong cash flow
        """,
        bear_arguments="""
        - iPhone sales plateauing
        - China headwinds
        - Limited innovation
        - Mature market
        """,
        final_decision="HOLD - Wait for better entry point",
        strategy={
            "action": "HOLD",
            "entry_price": None,
            "take_profit": None,
            "stop_loss": None,
            "position_size_pct": 0
        },
        metadata={"market_condition": "Bull market", "sector": "Technology"}
    )
    print(f"   Stored: {memory_id_3}")
    print()
    
    # Get statistics
    print("[3] Memory statistics:")
    stats = memory.get_statistics()
    print(f"   Total analyses: {stats['total_analyses']}")
    print(f"   Completed: {stats['completed_analyses']}")
    print(f"   Pending: {stats['pending_analyses']}")
    print()
    
    # Query similar situations
    print("[4] Testing similarity search...")
    print("   Query: 'High growth tech stock with valuation concerns'")
    
    similar = memory.get_similar_past_analyses(
        current_situation="High growth tech stock with extreme valuation but strong fundamentals",
        n_results=3,
        min_similarity=0.3
    )
    
    for i, result in enumerate(similar, 1):
        print(f"\n   Match {i}:")
        print(f"   Similarity: {result['similarity']:.2%}")
        print(f"   Ticker: {result['metadata']['ticker']}")
        print(f"   Action: {result['metadata']['action']}")
        print(f"   Outcome: {result['metadata']['outcome']}")
    print()
    
    # Update outcomes (simulating what happens after trade execution)
    print("[5] Updating outcomes...")
    
    # NVDA SELL was correct (price fell)
    memory.update_outcome(
        memory_id=memory_id_1,
        actual_outcome="Price declined as predicted",
        profit_loss_pct=15.2,  # Made money by selling
        lessons_learned="High valuation concerns proved correct. Trust the bear case when P/E > 100x."
    )
    print(f"   Updated {memory_id_1}: +15.2% profit")
    
    # TSLA BUY was correct (hit target)
    memory.update_outcome(
        memory_id=memory_id_2,
        actual_outcome="Hit take profit target",
        profit_loss_pct=17.0,
        lessons_learned="Momentum trading works when delivery numbers strong. Trust the data."
    )
    print(f"   Updated {memory_id_2}: +17.0% profit")
    
    # AAPL HOLD - missed rally (mistake)
    memory.update_outcome(
        memory_id=memory_id_3,
        actual_outcome="Missed rally - Apple Intelligence announcement",
        profit_loss_pct=-8.5,  # Lost opportunity
        lessons_learned="Don't underestimate Apple's ability to innovate. Services growth was undervalued."
    )
    print(f"   Updated {memory_id_3}: -8.5% (missed opportunity)")
    print()
    
    # Get updated statistics
    print("[6] Updated memory statistics:")
    stats = memory.get_statistics()
    print(f"   Total analyses: {stats['total_analyses']}")
    print(f"   Completed: {stats['completed_analyses']}")
    print(f"   Win rate: {stats['win_rate']:.1f}%")
    print(f"   Average P/L: {stats['average_pnl']:+.2f}%")
    print()
    
    # Get past mistakes
    print("[7] Learning from past mistakes...")
    mistakes = memory.get_past_mistakes(min_loss_pct=-10.0, n_results=2)
    
    for i, mistake in enumerate(mistakes, 1):
        print(f"\n   Mistake {i}:")
        print(f"   Ticker: {mistake['metadata']['ticker']}")
        print(f"   Loss: {mistake['metadata']['profit_loss_pct']}%")
        print(f"   Lesson: {mistake['metadata'].get('lessons_learned', 'N/A')}")
    print()
    
    # Get success patterns
    print("[8] Identifying success patterns...")
    successes = memory.get_success_patterns(min_profit_pct=10.0, n_results=2)
    
    for i, success in enumerate(successes, 1):
        print(f"\n   Success {i}:")
        print(f"   Ticker: {success['metadata']['ticker']}")
        print(f"   Profit: {success['metadata']['profit_loss_pct']}%")
        print(f"   Lesson: {success['metadata'].get('lessons_learned', 'N/A')}")
    print()
    
    # Test ticker-specific query
    print("[9] Testing ticker-specific query...")
    print("   Query: Similar NVDA analyses")
    
    nvda_similar = memory.get_similar_past_analyses(
        current_situation="NVIDIA with strong growth but high valuation",
        ticker="NVDA",
        n_results=2
    )
    
    print(f"   Found {len(nvda_similar)} similar NVDA analyses")
    print()
    
    print("="*80)
    print("✅ MEMORY SYSTEM TEST COMPLETED SUCCESSFULLY!")
    print("="*80)
    print()
    print("Next steps:")
    print("1. Memory system is working and persisted to ./test_chroma_db")
    print("2. Integrate into Bull/Bear researchers in research_team.py")
    print("3. Initialize in main.py on server startup")
    print("4. Add /memory endpoint for debugging")
    print()


if __name__ == "__main__":
    try:
        test_memory_system()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
