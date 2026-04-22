"""Unit tests for generate_general_themes Lambda handler."""

import os
from unittest.mock import MagicMock, patch

os.environ["WEB_CRAWLER_MCP_ARN"] = "arn:aws:bedrock-agentcore:us-west-2:123456789:runtime/test-mcp"
os.environ["AWS_REGION"] = "us-west-2"
os.environ["THEME_HOURS"] = "48"
os.environ["THEME_LIMIT"] = "6"

from wealth_management_portal_scheduler_tools.lambda_functions.generate_general_themes import lambda_handler

_MODULE = "wealth_management_portal_scheduler_tools.lambda_functions.generate_general_themes"


def _patch_invoke(side_effect=None, crawl_result=None, theme_result=None):
    """Patch _invoke_web_crawler_mcp; side_effect takes priority over results."""
    if side_effect is not None:
        return patch(f"{_MODULE}._invoke_web_crawler_mcp", side_effect=side_effect)
    results = iter([crawl_result, theme_result])
    return patch(f"{_MODULE}._invoke_web_crawler_mcp", side_effect=lambda *a, **kw: next(results))


def test_handler_success():
    """Happy path — crawl then theme generation, handler returns 200 with both results."""
    crawl_result = {"success": True, "articles_saved": 12, "duplicates": 3, "message": "Saved 12 articles"}
    theme_result = {
        "success": True,
        "themes_generated": 4,
        "themes": [],
        "message": "Successfully generated 4 general market themes",
    }
    with _patch_invoke(crawl_result=crawl_result, theme_result=theme_result):
        result = lambda_handler({}, MagicMock())

    assert result["statusCode"] == 200
    assert result["themes_generated"] == 4
    assert result["articles_saved"] == 12
    assert "timestamp" in result


def test_handler_crawl_failure_continues():
    """Crawl fails but handler continues with existing articles and still generates themes."""
    crawl_result = {"success": False, "error": "Feed timeout"}
    theme_result = {"success": True, "themes_generated": 2, "message": "Generated 2 themes"}
    with _patch_invoke(crawl_result=crawl_result, theme_result=theme_result):
        result = lambda_handler({}, MagicMock())

    assert result["statusCode"] == 200
    assert result["themes_generated"] == 2


def test_handler_uses_env_vars():
    """Verify hours and limit are read from env vars."""
    crawl_result = {"success": True, "articles_saved": 5, "duplicates": 0}
    theme_result = {"success": True, "themes_generated": 3, "message": "done"}
    with (
        patch.dict(os.environ, {"THEME_HOURS": "24", "THEME_LIMIT": "3"}),
        _patch_invoke(crawl_result=crawl_result, theme_result=theme_result),
    ):
        result = lambda_handler({}, MagicMock())

    assert result["statusCode"] == 200
    assert result["hours"] == 24


def test_handler_mcp_returns_failure():
    """Theme tool returns success=False — handler returns 500."""
    crawl_result = {"success": True, "articles_saved": 5, "duplicates": 0}
    theme_result = {"success": False, "error": "Redshift connection failed"}
    with _patch_invoke(crawl_result=crawl_result, theme_result=theme_result):
        result = lambda_handler({}, MagicMock())

    assert result["statusCode"] == 500
    assert "Redshift connection failed" in result["error"]


def test_handler_missing_arn():
    """Missing WEB_CRAWLER_MCP_ARN env var — handler returns 500."""
    with patch.dict(os.environ, {"WEB_CRAWLER_MCP_ARN": ""}):
        result = lambda_handler({}, MagicMock())

    assert result["statusCode"] == 500
    assert "WEB_CRAWLER_MCP_ARN" in result["error"]


def test_handler_transport_exception():
    """Transport-level exception — handler returns 500 with traceback."""
    with _patch_invoke(side_effect=Exception("Connection refused")):
        result = lambda_handler({}, MagicMock())

    assert result["statusCode"] == 500
    assert "Connection refused" in result["error"]
    assert "traceback" in result
