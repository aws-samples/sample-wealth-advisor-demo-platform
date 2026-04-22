#!/usr/bin/env python3
"""
Local crawler test — runs the fixed crawler and saves new articles directly to Redshift.
No deployment needed. Uses the same IAM connection as portfolio_data_server.

Usage:
  cd wealth-management-portal
  uv run python scripts/crawl-and-save-articles-local.py
  uv run python scripts/crawl-and-save-articles-local.py --dry-run        # don't save, just show what would be saved
  uv run python scripts/crawl-and-save-articles-local.py --max-sources 3  # limit to first 3 feeds
"""

import argparse
import os
import sys
from contextlib import contextmanager
from datetime import datetime

# Ensure the project packages are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))


def get_conn_factory():
    from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory
    return iam_connection_factory()


@contextmanager
def conn_ctx(connect_fn):
    conn = connect_fn()
    try:
        yield conn
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Crawl RSS feeds and save new articles to Redshift locally")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and deduplicate but do not write to Redshift")
    parser.add_argument("--max-sources", type=int, default=None, help="Limit to first N RSS sources")
    args = parser.parse_args()

    connect_fn = get_conn_factory()

    # Step 1: load existing URLs from Redshift for dedup
    print("[local] Fetching existing article URLs from Redshift...")
    from wealth_management_portal_portfolio_data_access.repositories.article_repository import ArticleRepository

    repo = ArticleRepository(lambda: conn_ctx(connect_fn).__enter__())

    # Use a proper context manager wrapper
    class ConnFactory:
        def __enter__(self):
            self._conn = connect_fn()
            return self._conn
        def __exit__(self, *args):
            self._conn.close()

    repo = ArticleRepository(ConnFactory)
    existing_urls = repo.get_existing_urls()
    print(f"[local] {len(existing_urls)} existing URLs loaded")

    # Step 2: crawl with URL-based dedup
    from wealth_management_portal_web_crawler.web_crawler_mcp.crawler import MarketIntelligenceCrawler

    crawler = MarketIntelligenceCrawler(rss_only=True, existing_urls=existing_urls)
    articles, stats = crawler.crawl_all_sources(max_sources=args.max_sources)

    print(f"\n[local] Crawl complete:")
    print(f"  new articles : {stats.new_articles}")
    print(f"  duplicates   : {stats.duplicates}")
    print(f"  errors       : {stats.errors}")

    if not articles:
        print("[local] No new articles to save.")
        return

    if args.dry_run:
        print(f"\n[local] DRY RUN — would save {len(articles)} articles:")
        for a in articles[:20]:
            print(f"  {a.source:20s} | {str(a.published_date)[:16]} | {a.title[:70]}")
        if len(articles) > 20:
            print(f"  ... and {len(articles) - 20} more")
        return

    # Step 3: save to Redshift
    print(f"\n[local] Saving {len(articles)} articles to Redshift...")
    saved = 0
    errors = []
    for article in articles:
        try:
            repo.save(article)
            saved += 1
            if saved % 10 == 0:
                print(f"[local] Saved {saved}/{len(articles)}...")
        except Exception as e:
            errors.append(f"{article.url}: {e}")

    print(f"\n[local] Done: saved={saved}, errors={len(errors)}")
    if errors:
        print("[local] Errors:")
        for e in errors[:10]:
            print(f"  {e}")


if __name__ == "__main__":
    main()
