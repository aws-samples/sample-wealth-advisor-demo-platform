"""Tests for common/streaming.py — SSE event helpers."""

import json

from wealth_management_portal_advisor_chat.common.streaming import (
    done_event,
    error_event,
    status_event,
    token_event,
)


def test_status_event():
    raw = status_event("Working...")
    assert raw.startswith("event: status\n")
    data = json.loads(raw.split("data: ")[1])
    assert data == {"message": "Working..."}


def test_token_event():
    raw = token_event("hello")
    assert raw.startswith("event: token\n")
    data = json.loads(raw.split("data: ")[1])
    assert data == {"text": "hello"}


def test_done_event_text_only():
    raw = done_event("Final answer")
    data = json.loads(raw.split("data: ")[1])
    assert data == {"message": "Final answer"}
    assert "stockData" not in data


def test_done_event_with_market_data():
    md = {"quotes": [{"symbol": "AAPL"}]}
    raw = done_event("Answer", market_data=md)
    data = json.loads(raw.split("data: ")[1])
    assert data["message"] == "Answer"
    assert data["marketData"] == md


def test_done_event_with_stock_data():
    sd = {"price": 150}
    raw = done_event("Answer", stock_data=sd)
    data = json.loads(raw.split("data: ")[1])
    assert data["stockData"] == sd


def test_error_event():
    raw = error_event("Something broke")
    assert raw.startswith("event: error\n")
    data = json.loads(raw.split("data: ")[1])
    assert data == {"message": "Something broke"}
