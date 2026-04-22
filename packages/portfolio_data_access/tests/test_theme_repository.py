"""
Unit tests for ThemeRepository and ThemeArticleRepository
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest

from wealth_management_portal_portfolio_data_access.models.market import Theme, ThemeArticleAssociation
from wealth_management_portal_portfolio_data_access.repositories.theme_repository import (
    ThemeArticleRepository,
    ThemeRepository,
)


@pytest.fixture
def mock_conn_factory():
    """Create a mock connection factory that returns a context manager"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Set up context manager for connection
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)

    # Set up context manager for cursor
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)

    mock_conn.cursor = Mock(return_value=mock_cursor)

    # Mock factory function
    factory = Mock(return_value=mock_conn)

    return factory, mock_conn, mock_cursor


@pytest.fixture
def theme_repository(mock_conn_factory):
    """Create ThemeRepository with mock connection factory"""
    factory, _, _ = mock_conn_factory
    return ThemeRepository(factory)


@pytest.fixture
def theme_article_repository(mock_conn_factory):
    """Create ThemeArticleRepository with mock connection factory"""
    factory, _, _ = mock_conn_factory
    return ThemeArticleRepository(factory)


@pytest.fixture
def sample_theme():
    """Create a sample theme for testing"""
    return Theme(
        theme_id="theme_123",
        client_id="__GENERAL__",
        title="Test Theme",
        sentiment="bullish",
        article_count=5,
        sources='["Source1", "Source2"]',  # JSON string
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        summary="Test summary",
        updated_at=datetime(2024, 1, 1, 12, 0, 0),
        score=85.5,
        rank=1,
        score_breakdown='{"article_count_score": 30, "source_diversity_score": 25}',  # JSON string
        generated_at=datetime(2024, 1, 1, 12, 0, 0),
        ticker="AAPL",
        relevance_score=95.0,
        combined_score=90.0,
        matched_tickers='["AAPL"]',  # JSON string
        relevance_reasoning="Test reasoning",
    )


def test_save_theme(theme_repository, mock_conn_factory, sample_theme):
    """Test saving a theme"""
    _, mock_conn, mock_cursor = mock_conn_factory

    theme_repository.save(sample_theme)

    # Verify execute was called
    assert mock_cursor.execute.called
    call_args = mock_cursor.execute.call_args[0][0]

    # Verify SQL uses plain INSERT (MERGE not supported on this Redshift cluster)
    assert "INSERT INTO" in call_args
    assert "themes" in call_args


def test_get_general_themes(theme_repository, mock_conn_factory, sample_theme):
    """Test getting general themes"""
    _, mock_conn, mock_cursor = mock_conn_factory

    # Mock return value
    mock_cursor.fetchall.return_value = [
        (
            sample_theme.theme_id,
            sample_theme.client_id,
            sample_theme.ticker,
            sample_theme.title,
            sample_theme.sentiment,
            sample_theme.article_count,
            sample_theme.sources,
            sample_theme.created_at,
            sample_theme.summary,
            sample_theme.updated_at,
            sample_theme.score,
            sample_theme.rank,
            sample_theme.score_breakdown,
            sample_theme.generated_at,
            sample_theme.relevance_score,
            sample_theme.combined_score,
            sample_theme.matched_tickers,
            sample_theme.relevance_reasoning,
        )
    ]
    mock_cursor.description = [
        ("theme_id",),
        ("client_id",),
        ("ticker",),
        ("title",),
        ("sentiment",),
        ("article_count",),
        ("sources",),
        ("created_at",),
        ("summary",),
        ("updated_at",),
        ("score",),
        ("rank",),
        ("score_breakdown",),
        ("generated_at",),
        ("relevance_score",),
        ("combined_score",),
        ("matched_tickers",),
        ("relevance_reasoning",),
    ]

    results = theme_repository.get_general_themes(limit=10)

    assert len(results) == 1
    assert results[0].theme_id == sample_theme.theme_id

    # Verify SQL
    call_args = mock_cursor.execute.call_args[0][0]
    assert "client_id" in call_args
    assert "LIMIT" in call_args


def test_get_portfolio_themes(theme_repository, mock_conn_factory, sample_theme):
    """Test getting portfolio themes for a client"""
    _, mock_conn, mock_cursor = mock_conn_factory

    # Mock return value - portfolio theme
    portfolio_theme_data = list(sample_theme.model_dump().values())
    portfolio_theme_data[1] = "CL00014"  # Change client_id

    mock_cursor.fetchall.return_value = [tuple(portfolio_theme_data)]
    mock_cursor.description = [
        ("theme_id",),
        ("client_id",),
        ("ticker",),
        ("title",),
        ("sentiment",),
        ("article_count",),
        ("sources",),
        ("created_at",),
        ("summary",),
        ("updated_at",),
        ("score",),
        ("rank",),
        ("score_breakdown",),
        ("generated_at",),
        ("relevance_score",),
        ("combined_score",),
        ("matched_tickers",),
        ("relevance_reasoning",),
    ]

    results = theme_repository.get_portfolio_themes(client_id="CL00014", limit=15)

    assert len(results) == 1
    assert results[0].client_id == "CL00014"

    # Verify SQL
    call_args = mock_cursor.execute.call_args[0][0]
    assert "client_id" in call_args
    assert "LIMIT" in call_args


def test_get_top_holdings_by_aum(theme_repository, mock_conn_factory):
    """Test getting top holdings by AUM"""
    _, mock_conn, mock_cursor = mock_conn_factory

    # Mock return value
    mock_cursor.fetchall.return_value = [
        ("AAPL", 1000000),
        ("GOOGL", 900000),
    ]
    mock_cursor.description = [("ticker",), ("aum_value",)]

    results = theme_repository.get_top_holdings_by_aum(client_id="CL00014", limit=5)

    assert len(results) == 2
    assert results[0]["ticker"] == "AAPL"
    assert results[1]["ticker"] == "GOOGL"

    # Verify SQL
    call_args = mock_cursor.execute.call_args[0][0]
    assert "holdings" in call_args
    assert "ORDER BY" in call_args
    assert "LIMIT" in call_args


def test_save_theme_article_association(theme_article_repository, mock_conn_factory):
    """Test saving theme-article association"""
    _, mock_conn, mock_cursor = mock_conn_factory

    association = ThemeArticleAssociation(
        theme_id="theme_123",
        article_hash="abc123",
        client_id="__GENERAL__",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
    )

    theme_article_repository.save(association)

    # Verify execute was called
    assert mock_cursor.execute.called
    call_args = mock_cursor.execute.call_args[0][0]

    # Verify SQL uses plain INSERT (MERGE not supported on this Redshift cluster)
    assert "INSERT INTO" in call_args
    assert "theme_article_associations" in call_args


def test_get_articles_for_theme(theme_article_repository, mock_conn_factory):
    """Test getting articles for a theme"""
    _, mock_conn, mock_cursor = mock_conn_factory

    # Mock return value
    mock_cursor.fetchall.return_value = [
        ("hash1",),
        ("hash2",),
        ("hash3",),
    ]
    mock_cursor.description = [("article_hash",)]

    results = theme_article_repository.get_articles_for_theme(theme_id="theme_123", client_id="__GENERAL__")

    assert len(results) == 3
    assert "hash1" in results
    assert "hash2" in results

    # Verify SQL
    call_args = mock_cursor.execute.call_args[0][0]
    assert "theme_id" in call_args
