"""Tests for graph_search_api."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from wealth_management_portal_graph_search_api.main import app

client = TestClient(app)


def test_get_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "default_node_limit" in data
    assert "node_types" in data


@patch("wealth_management_portal_graph_search_api.main.get_neptune_client")
def test_get_graph(mock_client):
    mock_nc = MagicMock()
    mock_client.return_value = mock_nc
    # Mock get_graph_data to return empty
    with patch(
        "wealth_management_portal_graph_search_api.main.get_graph_data", return_value={"nodes": [], "edges": []}
    ):
        response = client.get("/api/graph")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
