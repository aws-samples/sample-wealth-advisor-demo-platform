"""
Market Intelligence Web Crawler
Crawls financial news websites and extracts articles
"""

import hashlib
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime

import feedparser
import requests
from newspaper import Article as NewspaperArticle
from wealth_management_portal_common_market_events.models import Article

# Feed fetch timeouts (seconds), configurable via environment variables
FEED_CONNECT_TIMEOUT = int(os.environ.get("FEED_CONNECT_TIMEOUT", "5"))
FEED_READ_TIMEOUT = int(os.environ.get("FEED_READ_TIMEOUT", "10"))

logger = logging.getLogger(__name__)


@dataclass
class NewsSource:
    """Configuration for a news source"""

    name: str
    source_type: str
    url: str
    enabled: bool = True


@dataclass
class CrawlStats:
    """Statistics from a crawl operation"""

    total_crawled: int = 0
    new_articles: int = 0
    duplicates: int = 0
    errors: int = 0
    sources: dict[str, dict[str, int]] = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = {}


class MarketIntelligenceCrawler:
    """Main crawler class for fetching market news articles"""

    # Configure news sources - 13 WORKING RSS feeds
    SOURCES = [
        # Major Financial News (5 sources)
        NewsSource("Wall Street Journal", "rss", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
        NewsSource("Financial Times", "rss", "https://www.ft.com/markets?format=rss"),
        NewsSource("CNBC", "rss", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        NewsSource("MarketWatch", "rss", "https://www.marketwatch.com/rss/topstories"),
        NewsSource("Yahoo Finance", "rss", "https://finance.yahoo.com/news/rssindex"),
        # Investment & Analysis (3 sources)
        NewsSource("Benzinga", "rss", "https://www.benzinga.com/feed"),
        NewsSource("Motley Fool", "rss", "https://www.fool.com/feeds/index.aspx"),
        NewsSource("Insider Monkey", "rss", "https://www.insidermonkey.com/blog/feed/"),
        # Business Publications (2 sources)
        NewsSource("The Economist", "rss", "https://www.economist.com/finance-and-economics/rss.xml"),
        NewsSource("Fortune", "rss", "https://fortune.com/feed/"),
        # Crypto & Specialized (3 sources)
        NewsSource("CoinDesk", "rss", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        NewsSource("Crypto News", "rss", "https://cryptonews.com/news/feed/"),
        NewsSource("U.S. News Money", "rss", "https://www.usnews.com/rss/news"),
    ]

    def __init__(
        self, rss_only: bool = False, existing_hashes: set[str] | None = None, existing_urls: set[str] | None = None
    ):
        """
        Initialize crawler

        Args:
            rss_only: If True, only use RSS content without fetching full articles
            existing_hashes: Kept for backward compatibility (unused)
            existing_urls: Set of existing article URLs for deduplication
        """
        self.rss_only = rss_only
        self.existing_hashes = existing_hashes or set()  # kept for backward compat
        self.existing_urls = existing_urls or set()

    @staticmethod
    def calculate_content_hash(content: str) -> str:
        """Generate MD5 hash for content deduplication"""
        return hashlib.md5(content.encode("utf-8"), usedforsecurity=False).hexdigest()

    def is_duplicate(self, url: str) -> bool:
        """Check if article URL already exists"""
        return url in self.existing_urls

    def crawl_rss(self, source: NewsSource) -> tuple[list[Article], dict[str, int]]:
        """Crawl RSS feed and extract articles."""
        articles = []
        stats = {"crawled": 0, "new": 0, "duplicates": 0, "errors": 0}

        print(f"[crawler] Fetching RSS: {source.name}")
        logger.info("[crawler] Fetching RSS: %s url=%s", source.name, source.url)
        try:
            # Fetch with explicit timeouts to prevent hanging on unresponsive feeds
            user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            response = requests.get(
                source.url,
                headers={"User-Agent": user_agent},
                timeout=(FEED_CONNECT_TIMEOUT, FEED_READ_TIMEOUT),
            )
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if not feed.entries:
                print(f"[crawler] {source.name}: no entries found")
                logger.warning("[crawler] %s: no entries found", source.name)
                return articles, stats

            print(f"[crawler] {source.name}: {len(feed.entries)} entries, processing up to 10")
            logger.info("[crawler] %s: %d entries found", source.name, len(feed.entries))

            for entry in feed.entries[:10]:
                try:
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    summary = entry.get("summary", entry.get("description", ""))

                    if not title or not link:
                        continue

                    # URL-based dedup: skip if we've already saved this article
                    if self.is_duplicate(link):
                        stats["duplicates"] += 1
                        logger.debug("[crawler] %s: duplicate url skipped: %s", source.name, title[:60])
                        continue

                    if self.rss_only:
                        # Fall back to title if summary is missing/too short (e.g. Yahoo Finance, CoinDesk)
                        content = summary if len(summary) >= 50 else (title if len(title) >= 10 else "")
                        if not content:
                            continue
                    else:
                        article = NewspaperArticle(link)
                        article.set_headers(
                            {
                                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                                "Accept-Language": "en-US,en;q=0.9",
                            }
                        )
                        article.download()
                        article.parse()
                        content = article.text
                        if not content or len(content) < 100:
                            content = summary
                            if len(content) < 100:
                                continue

                    # Hash is md5(content) — used as PK only, dedup is by URL above
                    content_hash = self.calculate_content_hash(content)

                    # Get published date
                    pub_date = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    elif entry.get("published"):
                        try:
                            pub_date = datetime.fromisoformat(entry.get("published"))
                        except (ValueError, TypeError):
                            pub_date = datetime.now()
                    else:
                        pub_date = datetime.now()

                    article_data = Article(
                        content_hash=content_hash,
                        url=link,
                        title=title,
                        content=content[:5000],
                        summary=summary[:500] if summary else content[:500],
                        published_date=pub_date,
                        source=source.name,
                        author=entry.get("author", "Unknown"),
                        created_at=datetime.now(),
                    )

                    articles.append(article_data)
                    self.existing_urls.add(link)
                    stats["new"] += 1
                    logger.debug("[crawler] %s: new article: %s", source.name, title[:60])

                    time.sleep(0.5)

                except Exception as e:
                    stats["errors"] += 1
                    logger.warning("[crawler] %s: error processing entry: %s", source.name, e)
                    continue

        except Exception as e:
            stats["errors"] += 1
            print(f"[crawler] {source.name}: feed fetch error: {e}")
            logger.error("[crawler] %s: feed fetch error: %s", source.name, e)

        stats["crawled"] = len(articles)
        logger.info(
            "[crawler] %s: done new=%d duplicates=%d errors=%d",
            source.name,
            stats["new"],
            stats["duplicates"],
            stats["errors"],
        )
        return articles, stats

    def crawl_all_sources(self, max_sources: int | None = None) -> tuple[list[Article], CrawlStats]:
        """Crawl all configured sources.

        Args:
            max_sources: If set, limit crawling to the first N sources (useful for testing).
        """
        all_articles = []
        overall_stats = CrawlStats()

        enabled_sources = [s for s in self.SOURCES if s.enabled]
        if max_sources is not None:
            enabled_sources = enabled_sources[:max_sources]
        print(f"[crawler] crawl_all_sources: {len(enabled_sources)} sources to crawl (rss_only={self.rss_only})")
        logger.info("[crawler] crawl_all_sources: %d sources, rss_only=%s", len(enabled_sources), self.rss_only)

        for i, source in enumerate(enabled_sources, 1):
            print(f"[crawler] [{i}/{len(enabled_sources)}] Crawling: {source.name}")
            logger.info("[crawler] [%d/%d] Crawling: %s", i, len(enabled_sources), source.name)

            articles, source_stats = self.crawl_rss(source)
            all_articles.extend(articles)

            overall_stats.total_crawled += source_stats["crawled"]
            overall_stats.new_articles += source_stats["new"]
            overall_stats.duplicates += source_stats["duplicates"]
            overall_stats.errors += source_stats["errors"]
            overall_stats.sources[source.name] = source_stats

        print(
            f"[crawler] crawl_all_sources DONE: total_new={overall_stats.new_articles} "
            f"total_duplicates={overall_stats.duplicates} total_errors={overall_stats.errors}"
        )
        logger.info(
            "[crawler] crawl_all_sources DONE: new=%d duplicates=%d errors=%d",
            overall_stats.new_articles,
            overall_stats.duplicates,
            overall_stats.errors,
        )
        return all_articles, overall_stats
