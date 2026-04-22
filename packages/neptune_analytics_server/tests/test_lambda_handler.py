"""Tests for neptune_analytics_gateway Lambda handler dispatch logic."""

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("NEPTUNE_GRAPH_ID", "g-test")

from wealth_management_portal_neptune_analytics_server.lambda_functions import (  # noqa: E402
    neptune_analytics_gateway as handler_module,
)
from wealth_management_portal_neptune_analytics_server.lambda_functions.neptune_analytics_gateway import (  # noqa: E402
    lambda_handler,
)


def make_context(tool_name: str):
    ctx = MagicMock()
    ctx.client_context.custom = {"bedrockAgentCoreToolName": f"SomeTarget___{tool_name}"}
    return ctx


@pytest.fixture(autouse=True)
def reset_client():
    """Reset module-level client between tests."""
    handler_module._client = None
    yield
    handler_module._client = None


def test_execute_cypher_dispatches():
    with patch.object(handler_module, "_get_client") as mock_get:
        mock_get.return_value.execute_query.return_value = {"results": []}
        result = lambda_handler({"query": "RETURN 1"}, make_context("execute_cypher"))
    assert result == {"results": []}
    mock_get.return_value.execute_query.assert_called_once_with("RETURN 1")


def test_test_connection_dispatches():
    with patch.object(handler_module, "_get_client") as mock_get:
        mock_get.return_value.test_connection.return_value = True
        mock_get.return_value.graph_id = "g-test"
        mock_get.return_value.region = "us-west-2"
        result = lambda_handler({}, make_context("test_connection"))
    assert result["connected"] is True
    assert result["graph_id"] == "g-test"


def test_find_similar_clients_dispatches():
    with patch.object(handler_module, "_get_client") as mock_get:
        mock_get.return_value.execute_query.return_value = {"results": []}
        result = lambda_handler({"client_id": "c-123"}, make_context("find_similar_clients"))
    assert result == {"results": []}


def test_compute_degree_centrality_dispatches():
    with patch.object(handler_module, "_get_client") as mock_get:
        mock_get.return_value.execute_query.return_value = {"results": [{"nid": "n-1", "degree": 3}]}
        result = lambda_handler({"node_ids": ["n-1"]}, make_context("compute_degree_centrality"))
    assert result["n-1"] == 3


def test_unknown_tool_raises():
    with pytest.raises(ValueError, match="Unknown tool"):
        lambda_handler({}, make_context("nonexistent_tool"))


def test_missing_tool_name_raises():
    ctx = MagicMock()
    ctx.client_context.custom = {"bedrockAgentCoreToolName": ""}
    with pytest.raises(ValueError, match="Missing or invalid tool name"):
        lambda_handler({}, ctx)
