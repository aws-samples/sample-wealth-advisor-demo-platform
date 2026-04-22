"""Tests for data models."""

from wealth_management_portal_common_market_events.models import (
    Article,
    CrawlLog,
    Theme,
    ThemeArticleAssociation,
)


def test_article_creation():
    """Test article model creation."""
    article = Article(
        content_hash="test123",
        url="https://example.com/article",
        title="Test Article",
        source="Test Source",
    )
    assert article.content_hash == "test123"
    assert article.url == "https://example.com/article"
    assert article.title == "Test Article"


def test_theme_creation():
    """Test theme model creation."""
    theme = Theme(theme_id="theme_test_123", title="Test Theme", sentiment="bullish", article_count=5)
    assert theme.theme_id == "theme_test_123"
    assert theme.title == "Test Theme"
    assert theme.sentiment == "bullish"
    assert theme.client_id == "__GENERAL__"


def test_theme_article_association():
    """Test theme-article association model."""
    assoc = ThemeArticleAssociation(theme_id="theme_123", article_hash="article_456")
    assert assoc.theme_id == "theme_123"
    assert assoc.article_hash == "article_456"
    assert assoc.client_id == "__GENERAL__"


def test_crawl_log():
    """Test crawl log model."""
    log = CrawlLog(total_crawled=50, new_articles=30, duplicates=15, errors=5)
    assert log.total_crawled == 50
    assert log.new_articles == 30
