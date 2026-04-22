"""Tests for routing_agent/main.py — FastAPI endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from wealth_management_portal_advisor_chat.routing_agent.main import _strip_thinking, app


@pytest.fixture
def client():
    return TestClient(app)


# --- _strip_thinking ---


def test_strip_thinking_removes_tags():
    assert _strip_thinking("<thinking>internal</thinking>Answer") == "Answer"


def test_strip_thinking_no_tags():
    assert _strip_thinking("Clean text") == "Clean text"


def test_strip_thinking_multiline():
    text = "<thinking>\nstep 1\nstep 2\n</thinking>\nFinal answer"
    assert _strip_thinking(text) == "Final answer"


# --- POST /chat ---


@patch("wealth_management_portal_advisor_chat.routing_agent.main.create_agent")
def test_chat_sync(mock_agent_fn, client):
    mock_agent = MagicMock()
    mock_agent.return_value = "Brittney Wright has $8M AUM"
    mock_agent_fn.return_value = mock_agent

    resp = client.post("/chat", json={"message": "Tell me about Brittney", "session_id": "s1"})
    assert resp.status_code == 200
    data = resp.json()
    assert "Brittney" in data["message"]
    assert data["marketData"] is None


@patch("wealth_management_portal_advisor_chat.routing_agent.main.build_market_data")
@patch("wealth_management_portal_advisor_chat.routing_agent.main.create_agent")
def test_chat_sync_with_market_data(mock_agent_fn, mock_build, client):
    mock_agent = MagicMock()
    mock_agent.return_value = 'AAPL is at $150\n\n<!--CHART:["AAPL"]-->'
    mock_agent_fn.return_value = mock_agent
    mock_build.return_value = {"quotes": [{"symbol": "AAPL"}], "chartData": {}, "timeRange": "1M"}

    resp = client.post("/chat", json={"message": "AAPL price"})
    data = resp.json()
    assert data["marketData"] is not None
    assert data["marketData"]["quotes"][0]["symbol"] == "AAPL"


@patch("wealth_management_portal_advisor_chat.routing_agent.main.create_agent")
def test_chat_sync_error(mock_agent_fn, client):
    mock_agent_fn.side_effect = Exception("boom")
    resp = client.post("/chat", json={"message": "test"})
    assert resp.status_code == 200
    assert "error" in resp.json()["message"].lower()


# --- GET /chart ---


@patch("wealth_management_portal_advisor_chat.routing_agent.main.build_market_data")
def test_chart_endpoint(mock_build, client):
    mock_build.return_value = {
        "quotes": [{"symbol": "AAPL"}],
        "chartData": {"dates": ["Mar 01"], "series": []},
        "timeRange": "5D",
    }
    resp = client.get("/chart?tickers=AAPL&range=5D")
    assert resp.status_code == 200
    data = resp.json()
    assert data["timeRange"] == "5D"


# --- GET /health ---


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
