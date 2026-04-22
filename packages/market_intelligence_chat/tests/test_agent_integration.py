"""
Test agent integration and tool functionality
"""


def test_stock_service_import():
    """Test that stock service can be imported"""
    from wealth_management_portal_market_intelligence_chat.stock_service import StockDataService

    service = StockDataService()
    assert service is not None
    assert service.quote_cache_duration == 300
    assert service.historical_cache_duration == 3600


def test_query_parser_import():
    """Test that query parser can be imported"""
    from wealth_management_portal_market_intelligence_chat.query_parser import QueryParser

    parser = QueryParser()
    assert parser is not None
    assert parser.model_id == "us.anthropic.claude-3-5-sonnet-20241022-v2:0"


def test_agent_tools_import():
    """Test that agent tools can be imported"""
    from wealth_management_portal_market_intelligence_chat.chat_agent.agent import (
        analyze_stock,
        compare_stocks,
        generate_ai_response,
        get_related_themes,
        get_stock_quote,
        parse_stock_query,
    )

    # Verify all tools are callable
    assert callable(parse_stock_query)
    assert callable(get_stock_quote)
    assert callable(compare_stocks)
    assert callable(analyze_stock)
    assert callable(get_related_themes)
    assert callable(generate_ai_response)


def test_agent_context_manager():
    """Test that agent context manager works"""
    from wealth_management_portal_market_intelligence_chat.chat_agent.agent import get_agent

    with get_agent("test_session") as agent:
        assert agent is not None
        # Agent is successfully created


def test_period_params_conversion():
    """Test period parameter conversion"""
    from wealth_management_portal_market_intelligence_chat.stock_service import StockDataService

    service = StockDataService()

    # Test various time ranges
    assert service.get_period_params("1D") == ("1d", "5m")
    assert service.get_period_params("5D") == ("5d", "30m")
    assert service.get_period_params("1M") == ("1mo", "1d")
    assert service.get_period_params("6M") == ("6mo", "1d")
    assert service.get_period_params("YTD") == ("ytd", "1d")
    assert service.get_period_params("1Y") == ("1y", "1d")
    assert service.get_period_params("5Y") == ("5y", "1wk")
    assert service.get_period_params("MAX") == ("max", "1mo")

    # Test default
    assert service.get_period_params("INVALID") == ("1mo", "1d")


def test_fallback_parser():
    """Test fallback query parser"""
    from wealth_management_portal_market_intelligence_chat.query_parser import QueryParser

    parser = QueryParser()

    # Test fallback parsing
    parsed = parser._fallback_parse("Compare AAPL vs MSFT")

    assert parsed.intent == "compare"
    assert "AAPL" in parsed.tickers
    assert "MSFT" in parsed.tickers
    assert parsed.time_range == "1M"
    assert parsed.confidence == 0.5


def test_common_stocks_reference():
    """Test common stocks reference"""
    from wealth_management_portal_market_intelligence_chat.query_parser import QueryParser

    parser = QueryParser()

    assert "AAPL" in parser.common_stocks["tech"]
    assert "MSFT" in parser.common_stocks["tech"]
    assert "JPM" in parser.common_stocks["finance"]
    assert "JNJ" in parser.common_stocks["healthcare"]
    assert "XOM" in parser.common_stocks["energy"]
    assert "WMT" in parser.common_stocks["consumer"]
