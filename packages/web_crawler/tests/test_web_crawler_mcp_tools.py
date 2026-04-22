"""
Integration tests for Web Crawler MCP Server tools
Tests that tools properly use Portfolio MCP client
"""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from wealth_management_portal_web_crawler.web_crawler_mcp.server import mcp


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP client"""
    client = MagicMock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.call_tool_sync = Mock()
    return client


@pytest.fixture
def mock_crawler():
    """Create a mock crawler"""
    crawler = Mock()
    crawler.crawl_all_sources = Mock(
        return_value=(
            [],
            Mock(total_crawled=10, new_articles=5, duplicates=5, errors=0, sources={"Source1": 5, "Source2": 5}),
        )
    )
    return crawler


@pytest.mark.asyncio
async def test_crawl_articles_tool(mock_mcp_client):
    """Test crawl_articles MCP tool"""
    # Mock get_existing_article_hashes response - Portfolio MCP returns {"ok": True, "hashes": [...]}
    mock_mcp_client.call_tool_sync.return_value = {
        "content": [{"text": json.dumps({"ok": True, "hashes": ["hash1", "hash2", "hash3"]})}]
    }

    with (
        patch(
            "wealth_management_portal_web_crawler.web_crawler_mcp.server.get_portfolio_mcp_client",
            return_value=mock_mcp_client,
        ),
        patch(
            "wealth_management_portal_web_crawler.web_crawler_mcp.server.MarketIntelligenceCrawler"
        ) as mock_crawler_class,
    ):
        mock_crawler_instance = Mock()
        mock_crawler_instance.crawl_all_sources.return_value = (
            [],
            Mock(total_crawled=10, new_articles=5, duplicates=5, errors=0, sources={"Source1": 5, "Source2": 5}),
        )
        mock_crawler_class.return_value = mock_crawler_instance

        # Call the tool
        result = await mcp.call_tool("crawl_articles", {"rss_only": False})

        # Verify result
        assert result is not None
        result_data = json.loads(result[0].text)
        assert result_data["success"] is True
        assert result_data["total_crawled"] == 10
        assert result_data["new_articles"] == 5


@pytest.mark.asyncio
async def test_save_articles_to_redshift_tool(mock_mcp_client):
    """Test save_articles_to_redshift MCP tool"""
    # Mock get_existing_article_hashes response - Portfolio MCP returns {"ok": True, "hashes": [...]}
    mock_mcp_client.call_tool_sync.side_effect = [
        {"content": [{"text": json.dumps({"ok": True, "hashes": ["hash1", "hash2"]})}]},  # get_existing_article_hashes
        {"content": [{"text": json.dumps({"ok": True, "content_hash": "new_hash1"})}]},  # save_article call 1
    ]

    with (
        patch(
            "wealth_management_portal_web_crawler.web_crawler_mcp.server.get_portfolio_mcp_client",
            return_value=mock_mcp_client,
        ),
        patch(
            "wealth_management_portal_web_crawler.web_crawler_mcp.server.MarketIntelligenceCrawler"
        ) as mock_crawler_class,
    ):
        # Create mock articles
        from datetime import datetime

        mock_article1 = Mock()
        mock_article1.content_hash = "new_hash1"
        mock_article1.title = "Article 1"
        mock_article1.url = "https://example.com/1"
        mock_article1.source = "Source1"
        mock_article1.published_date = datetime(2024, 1, 1, 12, 0, 0)
        mock_article1.summary = "Summary 1"
        mock_article1.content = "Content 1"
        mock_article1.author = "Author 1"
        mock_article1.tags = ["tag1"]

        mock_crawler_instance = Mock()
        mock_crawler_instance.crawl_all_sources.return_value = (
            [mock_article1],
            Mock(total_crawled=10, new_articles=1, duplicates=9, errors=0, sources={"Source1": 10}),
        )
        mock_crawler_class.return_value = mock_crawler_instance

        # Call the tool
        result = await mcp.call_tool("save_articles_to_redshift", {"rss_only": False})

        # Verify result
        assert result is not None
        result_data = json.loads(result[0].text)
        assert result_data["success"] is True
        assert result_data["articles_saved"] == 1


@pytest.mark.asyncio
async def test_get_recent_articles_tool(mock_mcp_client):
    """Test get_recent_articles MCP tool"""
    # Mock get_recent_articles response - Portfolio MCP returns {"ok": True, "articles": [...]}
    mock_mcp_client.call_tool_sync.return_value = {
        "content": [
            {
                "text": json.dumps(
                    {
                        "ok": True,
                        "articles": [
                            {"content_hash": "hash1", "title": "Article 1"},
                            {"content_hash": "hash2", "title": "Article 2"},
                        ],
                    }
                )
            }
        ]
    }

    with patch(
        "wealth_management_portal_web_crawler.web_crawler_mcp.server.get_portfolio_mcp_client",
        return_value=mock_mcp_client,
    ):
        # Call the tool
        result = await mcp.call_tool("get_recent_articles", {"hours": 48, "limit": 100})

        # Verify result
        assert result is not None
        result_data = json.loads(result[0].text)
        assert result_data["success"] is True
        assert result_data["count"] == 2


@pytest.mark.asyncio
async def test_generate_general_themes_tool(mock_mcp_client):
    """Test generate_general_themes MCP tool"""
    # Mock responses - Portfolio MCP returns {"ok": True, ...}
    mock_mcp_client.call_tool_sync.side_effect = [
        {"content": [{"text": json.dumps({"ok": True})}]},  # save_theme
        {"content": [{"text": json.dumps({"ok": True})}]},  # save_theme_article_association
    ]

    with (
        patch(
            "wealth_management_portal_web_crawler.web_crawler_mcp.server.get_portfolio_mcp_client",
            return_value=mock_mcp_client,
        ),
        patch("wealth_management_portal_web_crawler.web_crawler_mcp.server.ThemeProcessor") as mock_processor_class,
    ):
        mock_processor = Mock()
        mock_theme = Mock()
        mock_theme.theme_id = "theme_123"
        mock_theme.title = "Test Theme"
        mock_theme.sentiment = "bullish"
        mock_theme.score = 85.5
        mock_theme.article_count = 5

        mock_processor.process_themes.return_value = ([mock_theme], {"theme_123": ["hash1", "hash2"]})
        mock_processor.save_themes_to_redshift = Mock()
        mock_processor_class.return_value = mock_processor

        # Call the tool
        result = await mcp.call_tool("generate_general_themes", {"hours": 48, "limit": 6})

        # Verify result
        assert result is not None
        result_data = json.loads(result[0].text)
        assert result_data["success"] is True
        assert result_data["themes_generated"] == 1


@pytest.mark.asyncio
async def test_generate_portfolio_themes_for_client_tool(mock_mcp_client):
    """Test generate_portfolio_themes_for_client MCP tool"""
    # Mock get_top_holdings_by_aum response - Portfolio MCP returns {"ok": True, "holdings": [...]}
    mock_mcp_client.call_tool_sync.side_effect = [
        {
            "content": [
                {
                    "text": json.dumps(
                        {
                            "ok": True,
                            "holdings": [
                                {"ticker": "AAPL", "security_name": "Apple Inc.", "aum_value": 1000000},
                                {"ticker": "GOOGL", "security_name": "Alphabet Inc.", "aum_value": 900000},
                            ],
                        }
                    )
                }
            ]
        },  # get_top_holdings_by_aum
        {"content": [{"text": json.dumps({"ok": True})}]},  # save_theme
        {"content": [{"text": json.dumps({"ok": True})}]},  # save_theme_article_association
    ]

    with (
        patch(
            "wealth_management_portal_web_crawler.web_crawler_mcp.server.get_portfolio_mcp_client",
            return_value=mock_mcp_client,
        ),
        patch(
            "wealth_management_portal_web_crawler.web_crawler_mcp.server.PortfolioThemeProcessor"
        ) as mock_processor_class,
    ):
        mock_processor = Mock()
        mock_theme = Mock()
        mock_theme.theme_id = "theme_123"
        mock_theme.title = "AAPL Theme"
        mock_theme.sentiment = "bullish"
        mock_theme.score = 85.5
        mock_theme.article_count = 3
        mock_theme.ticker = "AAPL"

        mock_processor.process_portfolio_themes.return_value = ([mock_theme], {"theme_123": ["hash1", "hash2"]})
        mock_processor.save_themes_to_redshift = Mock()
        mock_processor_class.return_value = mock_processor

        # Call the tool
        result = await mcp.call_tool(
            "generate_portfolio_themes_for_client",
            {"client_id": "CL00014", "top_n_stocks": 5, "themes_per_stock": 3, "hours": 48},
        )

        # Verify result
        assert result is not None
        result_data = json.loads(result[0].text)
        assert result_data["success"] is True
        assert result_data["client_id"] == "CL00014"
        assert result_data["themes_generated"] == 1
