"""
Unit tests for ArticleRepository
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest

from wealth_management_portal_portfolio_data_access.models.market import Article
from wealth_management_portal_portfolio_data_access.repositories.article_repository import ArticleRepository


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
def article_repository(mock_conn_factory):
    """Create ArticleRepository with mock connection factory"""
    factory, _, _ = mock_conn_factory
    return ArticleRepository(factory)


@pytest.fixture
def sample_article():
    """Create a sample article for testing"""
    return Article(
        content_hash="abc123",
        title="Test Article",
        url="https://example.com/article",
        source="Test Source",
        published_date=datetime(2024, 1, 1, 12, 0, 0),
        summary="Test summary",
        content="Test content",
        author="Test Author",
        file_path=None,
        created_at=datetime(2024, 1, 1, 12, 0, 0),
    )


def test_save_article(article_repository, mock_conn_factory, sample_article):
    """Test saving an article"""
    _, mock_conn, mock_cursor = mock_conn_factory

    article_repository.save(sample_article)

    # Verify execute was called
    assert mock_cursor.execute.called
    call_args = mock_cursor.execute.call_args[0][0]

    # Verify SQL contains INSERT
    assert "INSERT INTO" in call_args
    assert "articles" in call_args


def test_get_by_hash_found(article_repository, mock_conn_factory, sample_article):
    """Test getting article by hash when it exists"""
    _, mock_conn, mock_cursor = mock_conn_factory

    # Mock return value
    mock_cursor.fetchall.return_value = [
        (
            sample_article.content_hash,
            sample_article.url,
            sample_article.title,
            sample_article.content,
            sample_article.summary,
            sample_article.published_date,
            sample_article.source,
            sample_article.author,
            sample_article.file_path,
            sample_article.created_at,
        )
    ]
    mock_cursor.description = [
        ("content_hash",),
        ("url",),
        ("title",),
        ("content",),
        ("summary",),
        ("published_date",),
        ("source",),
        ("author",),
        ("file_path",),
        ("created_at",),
    ]

    result = article_repository.get_by_hash(sample_article.content_hash)

    assert result is not None
    assert result.content_hash == sample_article.content_hash
    assert result.title == sample_article.title


def test_get_by_hash_not_found(article_repository, mock_conn_factory):
    """Test getting article by hash when it doesn't exist"""
    _, mock_conn, mock_cursor = mock_conn_factory

    mock_cursor.fetchall.return_value = []

    result = article_repository.get_by_hash("nonexistent")

    assert result is None


def test_get_recent_articles(article_repository, mock_conn_factory, sample_article):
    """Test getting recent articles"""
    _, mock_conn, mock_cursor = mock_conn_factory

    # Mock return value
    mock_cursor.fetchall.return_value = [
        (
            sample_article.content_hash,
            sample_article.url,
            sample_article.title,
            sample_article.content,
            sample_article.summary,
            sample_article.published_date,
            sample_article.source,
            sample_article.author,
            sample_article.file_path,
            sample_article.created_at,
        )
    ]
    mock_cursor.description = [
        ("content_hash",),
        ("url",),
        ("title",),
        ("content",),
        ("summary",),
        ("published_date",),
        ("source",),
        ("author",),
        ("file_path",),
        ("created_at",),
    ]

    results = article_repository.get_recent(hours=48)

    assert len(results) == 1
    assert results[0].content_hash == sample_article.content_hash

    # Verify SQL contains time filter
    call_args = mock_cursor.execute.call_args[0][0]
    assert "created_at >=" in call_args


def test_get_existing_hashes(article_repository, mock_conn_factory):
    """Test getting existing article hashes"""
    _, mock_conn, mock_cursor = mock_conn_factory

    # Mock return value
    mock_cursor.fetchall.return_value = [
        ("hash1",),
        ("hash2",),
        ("hash3",),
    ]
    mock_cursor.description = [("content_hash",)]

    results = article_repository.get_existing_hashes()

    assert len(results) == 3
    assert "hash1" in results
    assert "hash2" in results
    assert "hash3" in results

    # Verify SQL
    call_args = mock_cursor.execute.call_args[0][0]
    assert "SELECT content_hash FROM" in call_args


def test_save_article_with_optional_fields(article_repository, mock_conn_factory):
    """Test saving article with optional fields as None"""
    _, mock_conn, mock_cursor = mock_conn_factory

    article = Article(
        content_hash="abc123",
        title="Test Article",
        url="https://example.com/article",
        source="Test Source",
        published_date=datetime(2024, 1, 1, 12, 0, 0),
        summary="Test summary",
        content="Test content",
        author=None,
        file_path=None,
        created_at=datetime(2024, 1, 1, 12, 0, 0),
    )

    article_repository.save(article)

    # Should not raise an error
    assert mock_cursor.execute.called
