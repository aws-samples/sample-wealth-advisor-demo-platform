"""Tests for common/market_data.py — chart data and market data builder."""

from unittest.mock import MagicMock, patch

import pandas as pd

from wealth_management_portal_advisor_chat.common.market_data import (
    PERIOD_MAP,
    build_market_data,
)

# --- PERIOD_MAP ---


def test_period_map_keys():
    expected = {"1D", "5D", "1M", "6M", "YTD", "1Y", "5Y", "MAX"}
    assert set(PERIOD_MAP.keys()) == expected


def test_period_map_1d():
    assert PERIOD_MAP["1D"] == ("1d", "5m")


# --- build_market_data ---


def _mock_ticker(price=150.0, prev=145.0, name="Test Inc"):
    tk = MagicMock()
    tk.info = {
        "currentPrice": price,
        "previousClose": prev,
        "shortName": name,
    }
    hist = pd.DataFrame(
        {"Close": [100.0, 102.0, 105.0], "Volume": [1000, 1100, 1200]},
        index=pd.to_datetime(["2025-03-01", "2025-03-02", "2025-03-03"]),
    )
    tk.history.return_value = hist
    return tk


@patch("wealth_management_portal_advisor_chat.common.market_data.yf.Ticker")
def test_build_market_data_basic(mock_yf):
    mock_yf.return_value = _mock_ticker()
    result = build_market_data({"tickers": ["AAPL"], "timeRange": "1M"})
    assert result is not None
    assert result["timeRange"] == "1M"
    assert len(result["quotes"]) == 1
    assert result["quotes"][0]["symbol"] == "AAPL"
    assert result["quotes"][0]["price"] == 150.0
    assert len(result["chartData"]["series"]) == 1


@patch("wealth_management_portal_advisor_chat.common.market_data.yf.Ticker")
def test_build_market_data_change_calc(mock_yf):
    mock_yf.return_value = _mock_ticker(price=150.0, prev=145.0)
    result = build_market_data({"tickers": ["AAPL"]})
    q = result["quotes"][0]
    assert q["change"] == 5.0
    assert q["changePercent"] == round((5.0 / 145.0) * 100, 2)


def test_build_market_data_no_tickers():
    result = build_market_data({"tickers": []})
    assert result is None


@patch("wealth_management_portal_advisor_chat.common.market_data.yf.Ticker")
def test_build_market_data_exception_returns_empty(mock_yf):
    mock_yf.side_effect = Exception("fail")
    # Clear lru_cache so mock takes effect
    from wealth_management_portal_advisor_chat.common.market_data import _fetch_history_cached, _get_ticker

    _get_ticker.cache_clear()
    _fetch_history_cached.cache_clear()
    result = build_market_data({"tickers": ["ZZZZ"]})
    assert result is not None
    assert result["quotes"] == []


@patch("wealth_management_portal_advisor_chat.common.market_data.yf.Ticker")
def test_build_market_data_compare_mode(mock_yf):
    mock_yf.return_value = _mock_ticker()
    result = build_market_data({"tickers": ["AAPL", "MSFT"]})
    assert result["compareMode"] == "normalized"


@patch("wealth_management_portal_advisor_chat.common.market_data.yf.Ticker")
def test_build_market_data_single_mode(mock_yf):
    mock_yf.return_value = _mock_ticker()
    result = build_market_data({"tickers": ["AAPL"]})
    assert result["compareMode"] == "absolute"
