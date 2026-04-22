#!/usr/bin/env python3
"""
Run generate_general_themes locally — no deployment needed.
Saves themes directly to Redshift via the repository (bypasses MCP save layer).

Requires SSM tunnel on localhost:5439.

Usage:
  cd wealth-management-portal
  uv run python scripts/generate-general-themes-local.py
  uv run python scripts/generate-general-themes-local.py --hours 48 --limit 6
"""

import argparse
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

import boto3
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient
from common_auth import SigV4HTTPXAuth
from wealth_management_portal_web_crawler.web_crawler_mcp.theme_generator import ThemeProcessor
from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory
from wealth_management_portal_portfolio_data_access.repositories.theme_repository import (
    ThemeRepository, ThemeArticleRepository
)
from wealth_management_portal_common_market_events.models import ThemeArticleAssociation


def get_local_portfolio_client() -> MCPClient:
    gateway_url = os.environ["PORTFOLIO_GATEWAY_URL"]
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    region = os.getenv("AWS_REGION", "us-east-1")
    auth = SigV4HTTPXAuth(credentials, region)
    return MCPClient(lambda: streamablehttp_client(gateway_url, auth=auth, timeout=120, terminate_on_close=False))


class ConnFactory:
    def __init__(self, connect_fn):
        self._connect_fn = connect_fn
    def __call__(self):
        return self
    def __enter__(self):
        self._conn = self._connect_fn()
        return self._conn
    def __exit__(self, *args):
        self._conn.close()


def save_themes_direct(themes, theme_articles_map, connect_fn):
    """Save themes directly via repository, bypassing MCP save layer."""
    factory = ConnFactory(connect_fn)
    theme_repo = ThemeRepository(factory)
    assoc_repo = ThemeArticleRepository(factory)

    for theme in themes:
        # Serialize dict fields to JSON strings for storage
        if isinstance(theme.score_breakdown, dict):
            theme.score_breakdown = json.dumps(theme.score_breakdown)
        if isinstance(theme.sources, list):
            theme.sources = json.dumps(theme.sources)
        if isinstance(theme.matched_tickers, list):
            theme.matched_tickers = json.dumps(theme.matched_tickers)

        theme_repo.save(theme)
        print(f"  saved theme: {theme.theme_id} — {theme.title[:60]}")

        for article_hash in theme_articles_map.get(theme.theme_id, []):
            assoc = ThemeArticleAssociation(
                theme_id=theme.theme_id,
                article_hash=article_hash,
                client_id="__GENERAL__",
                created_at=datetime.now(),
            )
            assoc_repo.save(assoc)


def main():
    parser = argparse.ArgumentParser(description="Generate general themes locally and save to Redshift")
    parser.add_argument("--hours", type=int, default=48)
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()

    connect_fn = iam_connection_factory()

    print(f"[local] Initializing ThemeProcessor (hours={args.hours}, limit={args.limit})...")
    mcp_client = get_local_portfolio_client()
    processor = ThemeProcessor(
        mcp_client=mcp_client,
        bedrock_region="us-east-1",
        use_cross_region=True,
    )

    print("[local] Fetching recent articles...")
    articles = processor.get_recent_articles(hours=args.hours)
    print(f"[local] Found {len(articles)} articles")

    if len(articles) < 3:
        print(f"[local] ERROR: Need at least 3 articles, found {len(articles)}")
        sys.exit(1)

    print("[local] Generating themes (calling Bedrock)...")
    themes, theme_articles_map = processor.process_themes(hours=args.hours, limit=args.limit)
    print(f"[local] Generated {len(themes)} themes:")
    for t in themes:
        print(f"  rank={t.rank} score={t.score:.2f} [{t.sentiment}] {t.title}")

    print("\n[local] Saving themes directly to Redshift...")
    save_themes_direct(themes, theme_articles_map, connect_fn)
    print(f"\n[local] Done — {len(themes)} themes saved.")


if __name__ == "__main__":
    main()
