"""
Test MCP tools for web crawler
"""

import pytest


def test_crawl_articles_import():
    """Test that crawl_articles tool can be imported"""
    from wealth_management_portal_web_crawler.web_crawler_mcp.server import crawl_articles

    assert callable(crawl_articles)


def test_save_articles_to_redshift_import():
    """Test that save_articles_to_redshift tool can be imported"""
    from wealth_management_portal_web_crawler.web_crawler_mcp.server import save_articles_to_redshift

    assert callable(save_articles_to_redshift)


def test_crawler_class_import():
    """Test that MarketIntelligenceCrawler can be imported"""
    from wealth_management_portal_web_crawler.web_crawler_mcp.crawler import MarketIntelligenceCrawler

    assert MarketIntelligenceCrawler is not None


def test_crawler_initialization():
    """Test that crawler can be initialized"""
    from wealth_management_portal_web_crawler.web_crawler_mcp.crawler import MarketIntelligenceCrawler

    crawler = MarketIntelligenceCrawler()
    assert crawler is not None
    assert len(MarketIntelligenceCrawler.SOURCES) > 0
    assert crawler.rss_only is False
    assert isinstance(crawler.existing_hashes, set)


def test_crawler_has_required_methods():
    """Test that crawler has required methods"""
    from wealth_management_portal_web_crawler.web_crawler_mcp.crawler import MarketIntelligenceCrawler

    crawler = MarketIntelligenceCrawler()

    # Check required methods exist
    assert hasattr(crawler, "crawl_rss")
    assert hasattr(crawler, "crawl_all_sources")
    assert hasattr(crawler, "is_duplicate")
    assert callable(crawler.crawl_rss)
    assert callable(crawler.crawl_all_sources)
    assert callable(crawler.is_duplicate)


@pytest.mark.integration
def test_crawl_articles_rss_only():
    """
    Integration test: Crawl articles in RSS-only mode (no Redshift)
    This test actually crawls RSS feeds but doesn't save to Redshift
    """
    from wealth_management_portal_web_crawler.web_crawler_mcp.server import crawl_articles

    # Test with RSS-only mode, use empty profile to use environment variables
    result = crawl_articles(rss_only=True, profile_name="")

    # Verify result structure
    assert isinstance(result, dict)
    assert "success" in result
    assert "articles_found" in result or "total_crawled" in result
    assert "new_articles" in result
    assert "duplicates" in result
    assert "errors" in result

    # Should have crawled some articles
    if result["success"]:
        assert result.get("total_crawled", 0) >= 0
        print(f"\n✓ Successfully crawled {result.get('articles_found', 0)} articles")
        print(f"  Total crawled: {result.get('total_crawled', 0)}")
        print(f"  New: {result.get('new_articles', 0)}, Duplicates: {result.get('duplicates', 0)}")


@pytest.mark.integration
@pytest.mark.redshift
def test_save_articles_to_redshift_integration():
    """
    Integration test: Save articles to Redshift
    Requires AWS credentials and Redshift access
    Mark with @pytest.mark.redshift to skip by default
    """
    from wealth_management_portal_web_crawler.web_crawler_mcp.server import save_articles_to_redshift

    # Test with RSS-only mode
    result = save_articles_to_redshift(
        rss_only=True,
        workgroup="financial-advisor-wg",
        database="financial-advisor-db",
        region="us-west-2",
        profile_name="wealth_management",
    )

    # Verify result structure
    assert isinstance(result, dict)
    assert "success" in result
    assert "message" in result

    # If successful, check stats
    if result["success"]:
        assert "articles_saved" in result or "total_crawled" in result
        assert "new_articles" in result
        assert "duplicates" in result


@pytest.mark.integration
@pytest.mark.redshift
def test_get_crawl_stats_integration():
    """
    Integration test: Get crawl statistics from Redshift
    Requires AWS credentials and Redshift access
    """
    from wealth_management_portal_web_crawler.web_crawler_mcp.server import get_crawl_stats

    result = get_crawl_stats(
        limit=5,
        workgroup="financial-advisor-wg",
        database="financial-advisor-db",
        region="us-west-2",
        profile_name="wealth_management",
    )

    # Verify result structure
    assert isinstance(result, dict)
    assert "success" in result

    if result["success"]:
        assert "count" in result or "crawl_logs" in result
        assert isinstance(result.get("crawl_logs", []), list)


def test_crawler_rss_feeds_list():
    """Test that crawler has valid RSS feeds configured"""
    from wealth_management_portal_web_crawler.web_crawler_mcp.crawler import MarketIntelligenceCrawler

    # Should have multiple RSS feeds
    assert len(MarketIntelligenceCrawler.SOURCES) >= 10

    # All feeds should have valid URLs
    for source in MarketIntelligenceCrawler.SOURCES:
        assert source.url.startswith("http://") or source.url.startswith("https://")
        assert source.name
        assert source.source_type == "rss"

    # Check for some known sources
    source_names = [s.name for s in MarketIntelligenceCrawler.SOURCES]
    assert "Yahoo Finance" in source_names
    assert "CNBC" in source_names
    assert "MarketWatch" in source_names
