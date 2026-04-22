from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from wealth_management_portal_intelligence_api.init import app

client = TestClient(app)


@patch("wealth_management_portal_intelligence_api.main.get_agent")
@patch("wealth_management_portal_intelligence_api.main.parse_stock_query")
def test_chat(mock_parse, mock_get_agent):
    mock_parse.return_value = {"tickers": [], "time_range": "1M"}
    mock_agent = MagicMock()
    mock_agent.__enter__ = MagicMock(return_value=mock_agent)
    mock_agent.__exit__ = MagicMock(return_value=False)
    mock_agent.return_value = "Test response"
    mock_get_agent.return_value = mock_agent

    response = client.post("/chat", json={"message": "hello", "session_id": "test"})
    assert response.status_code == 200
    assert "message" in response.json()
