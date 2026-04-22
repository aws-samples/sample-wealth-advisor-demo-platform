"""Tests for stock_data_agent/tools.py — live stock quotes."""

from unittest.mock import MagicMock, patch

from wealth_management_portal_advisor_chat.stock_data_agent.tools import (
    get_stock_quotes,
)


@patch("wealth_management_portal_advisor_chat.stock_data_agent.tools.yf.Ticker")
def test_get_stock_quotes(mock_yf):
    mock_tk = MagicMock()
    mock_tk.info = {
        "currentPrice": 150.0,
        "previousClose": 145.0,
        "shortName": "Apple Inc.",
        "sector": "Technology",
    }
    mock_yf.return_value = mock_tk

    result = get_stock_quotes._tool_func(tickers=["AAPL"])
    assert "| Metric |" in result
    assert "AAPL" in result
    assert "$150.00" in result
    assert "Technology" in result


@patch("wealth_management_portal_advisor_chat.stock_data_agent.tools.yf.Ticker")
def test_get_stock_quotes_error(mock_yf):
    mock_yf.side_effect = Exception("API error")
    result = get_stock_quotes._tool_func(tickers=["BAD"])
    assert "Could not fetch" in result
