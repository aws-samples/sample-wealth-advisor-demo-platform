#!/usr/bin/env python3
"""
Test script to demonstrate market intelligence chat responses
"""
import sys
import os
import json

# Add the package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from wealth_management_portal_market_intelligence_chat.chat_agent.agent import get_agent


def test_chat_query(query: str, test_name: str, session_id: str = "test_session"):
    """Test a single chat query and display the response"""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    print(f"Query: {query}")
    print(f"{'-'*80}")
    
    try:
        with get_agent(session_id) as agent:
            response = agent(query)
            print(f"Response:\n{response}")
            print(f"{'='*80}\n")
            return response
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")
        return None


def main():
    """Run various test queries against the chat agent"""
    print("Initializing Market Intelligence Chat Agent...")
    print("Testing various query types...\n")
    
    # Test 1: Simple stock quote
    test_chat_query(
        "What's the current price of Apple?",
        "Simple Stock Quote"
    )
    
    # Test 2: Stock comparison
    test_chat_query(
        "Compare Microsoft and Google stocks",
        "Stock Comparison"
    )
    
    # Test 3: Stock analysis
    test_chat_query(
        "Analyze Tesla stock performance",
        "Stock Analysis"
    )
    
    # Test 4: Related themes (requires coordinator agent)
    test_chat_query(
        "What are the market themes related to AAPL?",
        "Related Market Themes"
    )
    
    # Test 5: Multiple stocks
    test_chat_query(
        "Show me quotes for AAPL, MSFT, and TSLA",
        "Multiple Stock Quotes"
    )
    
    # Test 6: General market question
    test_chat_query(
        "What's happening in the tech sector?",
        "General Market Question"
    )
    
    print("\n" + "="*80)
    print("All tests completed!")
    print("="*80)


if __name__ == "__main__":
    main()
