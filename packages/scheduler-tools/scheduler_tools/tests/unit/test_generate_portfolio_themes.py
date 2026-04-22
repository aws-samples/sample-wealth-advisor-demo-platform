"""Unit tests for generate_portfolio_themes Lambda handler."""

import os
from unittest.mock import MagicMock, patch

os.environ["WEB_CRAWLER_MCP_ARN"] = "arn:aws:bedrock-agentcore:us-west-2:123456789:runtime/test-mcp"
os.environ["AWS_REGION"] = "us-west-2"
os.environ["TOP_N_STOCKS"] = "5"
os.environ["THEMES_PER_STOCK"] = "3"
os.environ["THEME_HOURS"] = "48"

from wealth_management_portal_scheduler_tools.lambda_functions.generate_portfolio_themes import lambda_handler

_MODULE = "wealth_management_portal_scheduler_tools.lambda_functions.generate_portfolio_themes"


def test_handler_success():
    """Happy path — MCP returns themes per stock, handler returns 200."""
    tool_result = {
        "success": True,
        "client_id": "CL00014",
        "themes_generated": 9,
        "stocks_covered": 3,
        "themes_by_stock": {"AAPL": [], "MSFT": [], "AMZN": []},
        "message": "Successfully generated 9 themes across 3 stocks for CL00014",
    }
    with patch(f"{_MODULE}._invoke_web_crawler_mcp", return_value=tool_result):
        result = lambda_handler({"client_id": "CL00014"}, MagicMock())

    assert result["statusCode"] == 200
    assert result["client_id"] == "CL00014"
    assert result["themes_generated"] == 9
    assert result["stocks_covered"] == 3


def test_handler_missing_client_id():
    """Missing client_id in event — handler returns 500."""
    result = lambda_handler({}, MagicMock())

    assert result["statusCode"] == 500
    assert "client_id is required" in result["error"]


def test_handler_missing_arn():
    """Missing WEB_CRAWLER_MCP_ARN — handler returns 500."""
    with patch.dict(os.environ, {"WEB_CRAWLER_MCP_ARN": ""}):
        result = lambda_handler({"client_id": "CL00014"}, MagicMock())

    assert result["statusCode"] == 500
    assert "WEB_CRAWLER_MCP_ARN" in result["error"]


def test_handler_mcp_returns_failure():
    """MCP tool returns success=False — handler returns 500."""
    tool_result = {"success": False, "error": "Client not found"}
    with patch(f"{_MODULE}._invoke_web_crawler_mcp", return_value=tool_result):
        result = lambda_handler({"client_id": "CL00014"}, MagicMock())

    assert result["statusCode"] == 500
    assert "Client not found" in result["error"]
    assert result["client_id"] == "CL00014"


def test_handler_uses_env_vars():
    """Verify top_n_stocks, themes_per_stock, hours are read from env vars."""
    tool_result = {"success": True, "themes_generated": 2, "stocks_covered": 1, "message": "done"}
    with (
        patch.dict(os.environ, {"TOP_N_STOCKS": "2", "THEMES_PER_STOCK": "1", "THEME_HOURS": "24"}),
        patch(f"{_MODULE}._invoke_web_crawler_mcp", return_value=tool_result),
    ):
        result = lambda_handler({"client_id": "CL00001"}, MagicMock())

    assert result["statusCode"] == 200
    assert result["top_n_stocks"] == 2
    assert result["themes_per_stock"] == 1
    assert result["hours"] == 24


def test_handler_transport_exception():
    """Transport-level exception — handler returns 500 with traceback."""
    with patch(f"{_MODULE}._invoke_web_crawler_mcp", side_effect=Exception("Timeout")):
        result = lambda_handler({"client_id": "CL00014"}, MagicMock())

    assert result["statusCode"] == 500
    assert "Timeout" in result["error"]
    assert result["client_id"] == "CL00014"
