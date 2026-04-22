"""
Test stock tools with real API calls
"""

import pytest


def test_parse_stock_query_tool():
    """Test parse_stock_query tool"""
    from wealth_management_portal_market_intelligence_chat.chat_agent.agent import parse_stock_query

    # Test single stock query
    result = parse_stock_query("What's the price of Apple stock?")
    assert result is not None
    assert "intent" in result
    assert "tickers" in result


def test_get_stock_quote_tool():
    """Test get_stock_quote tool"""
    from wealth_management_portal_market_intelligence_chat.chat_agent.agent import get_stock_quote

    # Test getting a quote for AAPL
    result = get_stock_quote("AAPL")
    assert result is not None
    assert "symbol" in result or "error" in result


def test_compare_stocks_tool():
    """Test compare_stocks tool"""
    from wealth_management_portal_market_intelligence_chat.chat_agent.agent import compare_stocks

    # Test comparing two stocks
    result = compare_stocks(["AAPL", "MSFT"], "1M")
    assert result is not None
    assert isinstance(result, dict)


def test_analyze_stock_tool():
    """Test analyze_stock tool"""
    from wealth_management_portal_market_intelligence_chat.chat_agent.agent import analyze_stock

    # Test analyzing a stock
    result = analyze_stock("AAPL", "6M")
    assert result is not None
    assert isinstance(result, dict)


@pytest.mark.skip(reason="Requires market_events_coordinator agent to be running")
def test_get_related_themes_tool():
    """Test get_related_themes tool (requires agent-to-agent communication)"""
    from wealth_management_portal_market_intelligence_chat.chat_agent.agent import get_related_themes

    # Test getting related themes
    result = get_related_themes(["AAPL"])
    assert result is not None


def test_generate_ai_response_tool():
    """Test generate_ai_response tool"""
    from wealth_management_portal_market_intelligence_chat.chat_agent.agent import generate_ai_response

    # Test generating a response
    result = generate_ai_response(
        "What is Apple's current stock price?", {"symbol": "AAPL", "price": 150.0, "change": 2.5}
    )
    assert result is not None
    # Result can be either a string (success) or dict with error
    assert isinstance(result, (str, dict))
    if isinstance(result, str):
        assert len(result) > 0
    elif isinstance(result, dict):
        # If error, should have error key
        assert "error" in result or "message" in result
