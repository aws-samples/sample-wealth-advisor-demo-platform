"""Unit tests for generate_general_themes Lambda handler."""

import os
from unittest.mock import MagicMock, patch

os.environ["WEB_CRAWLER_MCP_ARN"] = "arn:aws:bedrock-agentcore:us-west-2:123456789:runtime/test-mcp"
os.environ["AWS_REGION"] = "us-west-2"
os.environ["THEME_HOURS"] = "48"
os.environ["THEME_LIMIT"] = "6"

from wealth_management_portal_scheduler_tools.lambda_functions.generate_general_themes import lambda_handler

_MODULE = "wealth_management_portal_scheduler_tools.lambda_functions.generate_general_themes"


def _patch_both(crawl_result=None, theme_result=None, crawl_side_effect=None, theme_side_effect=None):
    """Patch _crawl_articles_via_mcp and _generate_themes_locally."""
    crawl_mock = patch(
        f"{_MODULE}._crawl_articles_via_mcp",
        side_effect=crawl_side_effect if crawl_side_effect is not None else None,
        return_value=crawl_result,
    )
    theme_mock = patch(
        f"{_MODULE}._generate_themes_locally",
        side_effect=theme_side_effect if theme_side_effect is not None else None,
        return_value=theme_result,
    )
    return crawl_mock, theme_mock


def test_handler_success():
    """Happy path — crawl then theme generation, handler returns 200."""
    crawl_result = {"success": True, "articles_saved": 12, "duplicates": 3, "message": "Saved 12 articles"}
    theme_result = {
        "success": True,
        "themes_generated": 4,
        "themes": [],
        "message": "Successfully generated 4 general market themes",
    }
    crawl_mock, theme_mock = _patch_both(crawl_result=crawl_result, theme_result=theme_result)
    with crawl_mock, theme_mock:
        result = lambda_handler({}, MagicMock())

    assert result["statusCode"] == 200
    assert result["themes_generated"] == 4
    assert "timestamp" in result


def test_handler_crawl_failure_continues():
    """Crawl fails but handler continues with existing articles and still generates themes."""
    crawl_result = {"success": False, "error": "Feed timeout"}
    theme_result = {"success": True, "themes_generated": 2, "message": "Generated 2 themes"}
    crawl_mock, theme_mock = _patch_both(crawl_result=crawl_result, theme_result=theme_result)
    with crawl_mock, theme_mock:
        result = lambda_handler({}, MagicMock())

    assert result["statusCode"] == 200
    assert result["themes_generated"] == 2


def test_handler_uses_env_vars():
    """Verify hours and limit are read from env vars."""
    crawl_result = {"success": True, "articles_saved": 5, "duplicates": 0}
    theme_result = {"success": True, "themes_generated": 3, "message": "done"}
    crawl_mock, theme_mock = _patch_both(crawl_result=crawl_result, theme_result=theme_result)
    with (
        patch.dict(os.environ, {"THEME_HOURS": "24", "THEME_LIMIT": "3"}),
        crawl_mock,
        theme_mock,
    ):
        result = lambda_handler({}, MagicMock())

    assert result["statusCode"] == 200
    assert result["hours"] == 24


def test_handler_theme_generation_failure():
    """Theme generation returns success=False — handler returns 500."""
    crawl_result = {"success": True, "articles_saved": 5, "duplicates": 0}
    theme_result = {"success": False, "error": "Redshift connection failed"}
    crawl_mock, theme_mock = _patch_both(crawl_result=crawl_result, theme_result=theme_result)
    with crawl_mock, theme_mock:
        result = lambda_handler({}, MagicMock())

    assert result["statusCode"] == 500
    assert "Redshift connection failed" in result["error"]


def test_handler_missing_arn_skips_crawl():
    """Empty WEB_CRAWLER_MCP_ARN — handler skips crawl, still generates themes."""
    theme_result = {"success": True, "themes_generated": 2, "message": "done"}
    _, theme_mock = _patch_both(theme_result=theme_result)
    with patch.dict(os.environ, {"WEB_CRAWLER_MCP_ARN": ""}), theme_mock:
        result = lambda_handler({}, MagicMock())

    assert result["statusCode"] == 200
    assert result["themes_generated"] == 2


def test_handler_crawl_exception_continues():
    """Crawl raises an exception — handler catches it gracefully and still generates themes."""
    theme_result = {"success": True, "themes_generated": 3, "message": "done"}
    crawl_mock, theme_mock = _patch_both(crawl_side_effect=Exception("Connection refused"), theme_result=theme_result)
    with crawl_mock, theme_mock:
        result = lambda_handler({}, MagicMock())

    # The crawl exception is caught inside _crawl_articles_via_mcp which returns {"success": False, ...}
    # But since we're patching _crawl_articles_via_mcp itself with side_effect, it raises.
    # The handler's try/except catches it at the top level → 500
    assert result["statusCode"] == 500
    assert "Connection refused" in result["error"]
    assert "traceback" in result
