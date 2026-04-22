"""
Integration tests for Portfolio Data Lambda Gateway tools
Tests the article and theme Lambda tool handlers
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

from wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway import lambda_handler


def _make_context(tool_name):
    ctx = MagicMock()
    ctx.client_context.custom = {"bedrockAgentCoreToolName": f"target___{tool_name}"}
    return ctx


@patch(
    "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway._conn_factory",
)
def test_save_article_tool(mock_conn_factory_patch):
    """Test save_article Lambda tool"""
    mock_conn = MagicMock()
    mock_conn_factory_patch.return_value.__enter__ = Mock(return_value=mock_conn)
    mock_conn_factory_patch.return_value.__exit__ = Mock(return_value=False)

    result = lambda_handler(
        {
            "content_hash": "abc123",
            "title": "Test Article",
            "url": "https://example.com/article",
            "source": "Test Source",
            "published_date": "2024-01-01T12:00:00",
            "summary": "Test summary",
            "content": "Test content",
            "author": "Test Author",
        },
        _make_context("save_article"),
    )

    assert result is not None
    assert result["ok"] is True
    assert result["content_hash"] == "abc123"


@patch(
    "wealth_management_portal_portfolio_data_access.repositories.article_repository.ArticleRepository.get_existing_hashes"
)
@patch(
    "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway._conn_factory",
)
def test_get_existing_article_hashes_tool(mock_conn_factory_patch, mock_get_hashes):
    """Test get_existing_article_hashes Lambda tool"""
    mock_conn = MagicMock()
    mock_conn_factory_patch.return_value.__enter__ = Mock(return_value=mock_conn)
    mock_conn_factory_patch.return_value.__exit__ = Mock(return_value=False)
    mock_get_hashes.return_value = {"hash1", "hash2", "hash3"}

    result = lambda_handler({}, _make_context("get_existing_article_hashes"))

    assert result is not None
    assert result["ok"] is True
    assert len(result["hashes"]) == 3
    assert "hash1" in result["hashes"]
    assert "hash2" in result["hashes"]


@patch("wealth_management_portal_portfolio_data_access.repositories.article_repository.ArticleRepository.get_recent")
@patch(
    "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway._conn_factory",
)
def test_get_recent_articles_tool(mock_conn_factory_patch, mock_get_recent):
    """Test get_recent_articles Lambda tool"""
    mock_conn = MagicMock()
    mock_conn_factory_patch.return_value.__enter__ = Mock(return_value=mock_conn)
    mock_conn_factory_patch.return_value.__exit__ = Mock(return_value=False)

    from wealth_management_portal_portfolio_data_access.models.market import Article

    mock_article = Article(
        content_hash="abc123",
        title="Test Article",
        url="https://example.com/article",
        source="Test Source",
        published_date=datetime(2024, 1, 1, 12, 0, 0),
        summary="Test summary",
        content="Test content",
        author="Test Author",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    mock_get_recent.return_value = [mock_article]

    result = lambda_handler({"hours": 48}, _make_context("get_recent_articles"))

    assert result is not None
    assert result["ok"] is True
    assert len(result["articles"]) == 1
    assert result["articles"][0]["content_hash"] == "abc123"


@patch(
    "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway._conn_factory",
)
def test_save_theme_tool(mock_conn_factory_patch):
    """Test save_theme Lambda tool"""
    mock_conn = MagicMock()
    mock_conn_factory_patch.return_value.__enter__ = Mock(return_value=mock_conn)
    mock_conn_factory_patch.return_value.__exit__ = Mock(return_value=False)

    result = lambda_handler(
        {
            "theme_id": "theme_123",
            "client_id": "__GENERAL__",
            "title": "Test Theme",
            "sentiment": "bullish",
            "article_count": 5,
            "sources": '["Source1", "Source2"]',
            "summary": "Test summary",
            "score": 85.5,
            "rank": 1,
        },
        _make_context("save_theme"),
    )

    assert result is not None
    assert result["ok"] is True
    assert result["theme_id"] == "theme_123"


@patch(
    "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway._conn_factory",
)
def test_save_theme_article_association_tool(mock_conn_factory_patch):
    """Test save_theme_article_association Lambda tool"""
    mock_conn = MagicMock()
    mock_conn_factory_patch.return_value.__enter__ = Mock(return_value=mock_conn)
    mock_conn_factory_patch.return_value.__exit__ = Mock(return_value=False)

    result = lambda_handler(
        {
            "theme_id": "theme_123",
            "article_hash": "abc123",
            "client_id": "__GENERAL__",
        },
        _make_context("save_theme_article_association"),
    )

    assert result is not None
    assert result["ok"] is True


@patch(
    "wealth_management_portal_portfolio_data_access.repositories.theme_repository.ThemeRepository.get_top_holdings_by_aum"
)
@patch(
    "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway._conn_factory",
)
def test_get_top_holdings_by_aum_tool(mock_conn_factory_patch, mock_get_holdings):
    """Test get_top_holdings_by_aum Lambda tool"""
    mock_conn = MagicMock()
    mock_conn_factory_patch.return_value.__enter__ = Mock(return_value=mock_conn)
    mock_conn_factory_patch.return_value.__exit__ = Mock(return_value=False)

    mock_get_holdings.return_value = [
        {"ticker": "AAPL", "security_name": "Apple Inc.", "aum_value": 1000000},
        {"ticker": "GOOGL", "security_name": "Alphabet Inc.", "aum_value": 900000},
    ]

    result = lambda_handler({"client_id": "CL00014", "limit": 5}, _make_context("get_top_holdings_by_aum"))

    assert result is not None
    assert result["ok"] is True
    assert len(result["holdings"]) == 2
    assert result["holdings"][0]["ticker"] == "AAPL"


@patch("wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.create_simple_repos")
@patch(
    "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway._conn_factory",
)
def test_get_active_clients_tool(mock_conn_factory_patch, mock_create_repos):
    """Test get_active_clients Lambda tool"""
    from wealth_management_portal_portfolio_data_access.models.client import Client

    mock_conn = MagicMock()
    mock_conn_factory_patch.return_value.__enter__ = Mock(return_value=mock_conn)
    mock_conn_factory_patch.return_value.__exit__ = Mock(return_value=False)

    mock_clients = [
        Client(
            client_id="CL00014",
            client_first_name="John",
            client_last_name="Doe",
            segment="Premium",
            status="Active",
            email="john.doe@example.com",
            advisor_id="ADV001",
        ),
        Client(
            client_id="CL00015",
            client_first_name="Jane",
            client_last_name="Smith",
            segment="Premium",
            status="Active",
            email="jane.smith@example.com",
            advisor_id="ADV001",
        ),
        Client(
            client_id="CL00016",
            client_first_name="Bob",
            client_last_name="Johnson",
            segment="Standard",
            status="Active",
            email="bob.johnson@example.com",
            advisor_id="ADV002",
        ),
    ]

    mock_client_repo = Mock()
    mock_client_repo.get.return_value = mock_clients
    mock_create_repos.return_value = {"client": mock_client_repo}

    result = lambda_handler({}, _make_context("get_active_clients"))

    assert result is not None
    assert result["ok"] is True
    assert len(result["client_ids"]) == 3
    assert "CL00014" in result["client_ids"]
    assert "CL00015" in result["client_ids"]

    # Verify get was called with status="Active"
    mock_client_repo.get.assert_called_once_with(status="Active")
