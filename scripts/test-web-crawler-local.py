#!/usr/bin/env python3
"""
Local test for all Web Crawler MCP server tools.

Calls tool functions directly — bypasses the Portfolio MCP ARN entirely.
Uses iam_connection_factory() to connect to Redshift directly from local machine.
Credentials come from the wealth_management AWS profile.

Usage:
  cd wealth-management-portal
  uv run python scripts/test-web-crawler-local.py [--tool TOOL] [--client-id CL00014]

Tools: all, get_recent_articles, crawl_articles, save_articles_to_redshift,
       generate_general_themes, generate_portfolio_themes_for_client
"""

import argparse
import json
import os
import sys

# ── 1. Set env vars BEFORE any other imports ─────────────────────────────────
os.environ.setdefault("AWS_REGION", "us-west-2")
os.environ.setdefault("REDSHIFT_WORKGROUP", "financial-advisor-wg")
os.environ.setdefault("REDSHIFT_DATABASE", "financial-advisor-db")
os.environ.setdefault("AWS_ACCOUNT_ID", "507139572291")

# Use profile-based auth — clear any stale hardcoded keys from .env
for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
    os.environ.pop(key, None)
os.environ["AWS_PROFILE"] = "wealth_management"

# ── 2. Resolve credentials explicitly so boto3 clients all use the right ones ─
import boto3 as _boto3
_session = _boto3.Session(profile_name="wealth_management", region_name="us-west-2")
_creds = _session.get_credentials().get_frozen_credentials()
os.environ["AWS_ACCESS_KEY_ID"] = _creds.access_key
os.environ["AWS_SECRET_ACCESS_KEY"] = _creds.secret_key
if _creds.token:
    os.environ["AWS_SESSION_TOKEN"] = _creds.token
else:
    os.environ.pop("AWS_SESSION_TOKEN", None)
os.environ.pop("AWS_PROFILE", None)  # use explicit keys from here on

# ── 3. Build a direct Redshift connection factory (no MCP ARN needed) ─────────
from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory

_conn_factory = iam_connection_factory()

# ── 4. Import repositories for direct Redshift access ─────────────────────────
from wealth_management_portal_portfolio_data_access.repositories.article_repository import ArticleRepository
from wealth_management_portal_portfolio_data_access.repositories.theme_repository import ThemeRepository

# ── 5. Import web crawler tools ────────────────────────────────────────────────
from wealth_management_portal_web_crawler.web_crawler_mcp.crawler import MarketIntelligenceCrawler


def _print_result(name: str, result: dict):
    print(f"\n{'='*60}")
    print(f"  RESULT: {name}")
    print(f"{'='*60}")
    success = result.get("success", result.get("ok", "?"))
    print(f"  success: {success}")
    if not success:
        print(f"  ERROR:   {result.get('error', result.get('message', 'unknown'))}")
    print(json.dumps(result, indent=2, default=str)[:2000])
    print()
    return success


def test_get_recent_articles(hours=48, limit=10):
    print(f"\n>>> [1/5] get_recent_articles(hours={hours}, limit={limit})")
    try:
        repo = ArticleRepository(_conn_factory)
        articles = repo.get_recent(hours=hours, limit=limit)
        result = {
            "success": True,
            "count": len(articles),
            "articles": [a.model_dump(mode="json") for a in articles],
        }
        ok = _print_result("get_recent_articles", result)
        if ok:
            print(f"  ✓ {result['count']} articles returned")
            for a in articles[:3]:
                print(f"    - [{a.source}] {a.title[:80]}")
        return ok
    except Exception as e:
        result = {"success": False, "error": str(e)}
        _print_result("get_recent_articles", result)
        return False


def test_crawl_articles(rss_only=True):
    print(f"\n>>> [2/5] crawl_articles(rss_only={rss_only})")
    try:
        repo = ArticleRepository(_conn_factory)
        existing_hashes = repo.get_existing_hashes()
        print(f"  Got {len(existing_hashes)} existing hashes from Redshift")

        crawler = MarketIntelligenceCrawler(rss_only=rss_only, existing_hashes=existing_hashes)
        articles, stats = crawler.crawl_all_sources()

        result = {
            "success": True,
            "articles_found": len(articles),
            "total_crawled": stats.total_crawled,
            "new_articles": stats.new_articles,
            "duplicates": stats.duplicates,
            "errors": stats.errors,
            "sources": stats.sources,
        }
        ok = _print_result("crawl_articles", result)
        if ok:
            print(f"  ✓ articles_found={len(articles)}  duplicates={stats.duplicates}")
        return ok
    except Exception as e:
        result = {"success": False, "error": str(e)}
        _print_result("crawl_articles", result)
        return False


def test_save_articles_to_redshift(rss_only=True):
    print(f"\n>>> [3/5] save_articles_to_redshift(rss_only={rss_only})")
    try:
        repo = ArticleRepository(_conn_factory)
        existing_hashes = repo.get_existing_hashes()
        print(f"  Got {len(existing_hashes)} existing hashes from Redshift")

        crawler = MarketIntelligenceCrawler(rss_only=rss_only, existing_hashes=existing_hashes)
        articles, stats = crawler.crawl_all_sources()
        print(f"  Crawled {len(articles)} new articles, saving to Redshift...")

        saved = 0
        errors = []
        for article in articles:
            try:
                repo.save(article)
                saved += 1
                if saved % 10 == 0:
                    print(f"  Saved {saved}/{len(articles)}...")
            except Exception as e:
                errors.append(f"{article.content_hash}: {e}")

        result = {
            "success": True,
            "articles_saved": saved,
            "total_crawled": stats.total_crawled,
            "duplicates": stats.duplicates,
            "save_errors": errors,
        }
        ok = _print_result("save_articles_to_redshift", result)
        if ok:
            print(f"  ✓ saved={saved}  errors={len(errors)}")
        return ok
    except Exception as e:
        result = {"success": False, "error": str(e)}
        _print_result("save_articles_to_redshift", result)
        return False


def test_generate_general_themes(hours=48, limit=6):
    print(f"\n>>> [4/5] generate_general_themes(hours={hours}, limit={limit})")
    try:
        processor = _DirectThemeProcessor(bedrock_region="us-east-1", use_cross_region=True)
        themes, theme_articles_map = processor.process_themes(hours=hours, limit=limit)
        processor.save_themes_to_redshift(themes, theme_articles_map)

        result = {
            "success": True,
            "themes_generated": len(themes),
            "themes": [
                {"theme_id": t.theme_id, "title": t.title, "sentiment": t.sentiment, "score": t.score}
                for t in themes
            ],
        }
        ok = _print_result("generate_general_themes", result)
        if ok:
            for t in themes:
                print(f"    - [{t.sentiment}] {t.title}")
        return ok
    except Exception as e:
        result = {"success": False, "error": str(e)}
        _print_result("generate_general_themes", result)
        return False


def test_generate_portfolio_themes_for_client(client_id, top_n_stocks=5, themes_per_stock=3, hours=48):
    print(f"\n>>> [5/5] generate_portfolio_themes_for_client(client_id={client_id})")
    try:
        processor = _DirectPortfolioThemeProcessor(bedrock_region="us-east-1", use_cross_region=True)
        themes, theme_articles_map = processor.process_portfolio_themes(
            client_id=client_id,
            top_n_stocks=top_n_stocks,
            themes_per_stock=themes_per_stock,
            hours=hours,
        )
        processor.save_themes_to_redshift(themes, theme_articles_map)

        result = {
            "success": True,
            "themes_generated": len(themes),
            "stocks_covered": len(set(t.ticker for t in themes if t.ticker)),
        }
        ok = _print_result("generate_portfolio_themes_for_client", result)
        if ok:
            print(f"  ✓ themes={len(themes)}  stocks={result['stocks_covered']}")
        return ok
    except Exception as e:
        result = {"success": False, "error": str(e)}
        _print_result("generate_portfolio_themes_for_client", result)
        return False


# ── Direct Redshift subclasses (bypass MCP client) ────────────────────────────

from wealth_management_portal_web_crawler.web_crawler_mcp.theme_generator import (
    ThemeProcessor as _ThemeProcessor,
    PortfolioThemeProcessor as _PortfolioThemeProcessor,
)
from wealth_management_portal_portfolio_data_access.models.market import (
    Theme as _DBTheme,
    ThemeArticleAssociation as _DBThemeArticleAssociation,
)
from wealth_management_portal_portfolio_data_access.repositories.theme_repository import (
    ThemeRepository as _ThemeRepository,
    ThemeArticleRepository as _ThemeArticleRepository,
)
from wealth_management_portal_common_market_events.models import Article as _CMEArticle
from datetime import datetime as _datetime


def _to_cme_articles(db_articles):
    """Convert portfolio_data_access Articles → common_market_events Articles."""
    result = []
    for a in db_articles:
        try:
            result.append(_CMEArticle(**a.model_dump()))
        except Exception:
            pass
    return result


class _DirectThemeProcessor(_ThemeProcessor):
    """ThemeProcessor subclass that reads/writes Redshift directly (no MCP ARN)."""

    def __init__(self, bedrock_region="us-east-1", use_cross_region=True):
        import boto3
        from botocore.config import Config
        config = Config(region_name=bedrock_region, retries={"max_attempts": 3, "mode": "adaptive"})
        self.bedrock = boto3.client("bedrock-runtime", config=config)
        self.use_cross_region = use_cross_region
        self.model_id = (
            "us.anthropic.claude-3-5-sonnet-20241022-v2:0" if use_cross_region
            else "anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
        self.mcp_client = None  # not used

    def get_recent_articles(self, hours=48):
        repo = ArticleRepository(_conn_factory)
        db_articles = repo.get_recent(hours=hours, limit=500)
        articles = _to_cme_articles(db_articles)
        print(f"  [direct] get_recent_articles: {len(articles)} articles from Redshift")
        return articles

    def save_themes_to_redshift(self, themes, theme_articles_map):
        import json as _json
        theme_repo = _ThemeRepository(_conn_factory)
        assoc_repo = _ThemeArticleRepository(_conn_factory)

        for theme in themes:
            # portfolio_data_access.Theme stores lists/dicts as JSON strings
            sources = theme.sources if isinstance(theme.sources, str) else _json.dumps(theme.sources or [])
            score_breakdown = (
                theme.score_breakdown if isinstance(theme.score_breakdown, str)
                else _json.dumps(theme.score_breakdown) if theme.score_breakdown else None
            )
            matched_tickers = (
                theme.matched_tickers if isinstance(theme.matched_tickers, str)
                else _json.dumps(theme.matched_tickers) if theme.matched_tickers else None
            )

            db_theme = _DBTheme(
                theme_id=theme.theme_id,
                client_id=theme.client_id,
                ticker=theme.ticker,
                title=theme.title,
                sentiment=theme.sentiment,
                article_count=theme.article_count,
                sources=sources,
                created_at=theme.created_at or _datetime.now(),
                summary=theme.summary,
                updated_at=theme.updated_at or _datetime.now(),
                score=theme.score,
                rank=theme.rank,
                score_breakdown=score_breakdown,
                generated_at=theme.generated_at or _datetime.now(),
                relevance_score=theme.relevance_score,
                combined_score=theme.combined_score,
                matched_tickers=matched_tickers,
                relevance_reasoning=theme.relevance_reasoning,
            )
            theme_repo.save(db_theme)
            print(f"  [direct] saved theme: {theme.theme_id}")

            for article_hash in theme_articles_map.get(theme.theme_id, []):
                assoc = _DBThemeArticleAssociation(
                    theme_id=theme.theme_id,
                    article_hash=article_hash,
                    client_id=theme.client_id,
                    created_at=_datetime.now(),
                )
                assoc_repo.save(assoc)


class _DirectPortfolioThemeProcessor(_DirectThemeProcessor, _PortfolioThemeProcessor):
    """PortfolioThemeProcessor that reads/writes Redshift directly.

    MRO: _DirectPortfolioThemeProcessor → _DirectThemeProcessor → _PortfolioThemeProcessor → ThemeProcessor
    This ensures get_recent_articles and save_themes_to_redshift from _DirectThemeProcessor
    take precedence over the MCP-based implementations in ThemeProcessor.
    """

    def __init__(self, bedrock_region="us-east-1", use_cross_region=True):
        _DirectThemeProcessor.__init__(self, bedrock_region=bedrock_region, use_cross_region=use_cross_region)

    def process_portfolio_themes(self, client_id, top_n_stocks=5, themes_per_stock=3, hours=48):
        top_holdings = _ThemeRepository(_conn_factory).get_top_holdings_by_aum(
            client_id=client_id, limit=top_n_stocks
        )
        if not top_holdings:
            raise ValueError(f"No holdings found for client {client_id}")

        tickers = [h["ticker"] for h in top_holdings]
        print(f"  [direct] top holdings for {client_id}: {tickers}")

        all_themes = []
        all_map = {}
        for holding in top_holdings:
            ticker = holding["ticker"]
            security_name = holding.get("security_name")
            try:
                themes, tmap = self.generate_stock_specific_themes(
                    client_id=client_id,
                    ticker=ticker,
                    hours=hours,
                    themes_per_stock=themes_per_stock,
                    security_name=security_name,
                )
                all_themes.extend(themes)
                all_map.update(tmap)
                print(f"  [direct] {ticker}: {len(themes)} themes")
            except Exception as e:
                print(f"  [direct] {ticker}: failed — {e}")

        return all_themes, all_map


# ── CLI ────────────────────────────────────────────────────────────────────────

TOOL_MAP = {
    "get_recent_articles": test_get_recent_articles,
    "crawl_articles": test_crawl_articles,
    "save_articles_to_redshift": test_save_articles_to_redshift,
    "generate_general_themes": test_generate_general_themes,
    "generate_portfolio_themes_for_client": test_generate_portfolio_themes_for_client,
}


def main():
    parser = argparse.ArgumentParser(description="Local test for Web Crawler MCP tools (direct Redshift)")
    parser.add_argument("--tool", default="all", choices=["all"] + list(TOOL_MAP.keys()))
    parser.add_argument("--client-id", default="CL00014")
    parser.add_argument("--hours", type=int, default=48)
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--rss-only", action="store_true", default=True)
    args = parser.parse_args()

    print(f"\nAWS_REGION      : {os.environ.get('AWS_REGION')}")
    print(f"REDSHIFT_WG     : {os.environ.get('REDSHIFT_WORKGROUP')}")
    print(f"MODE            : direct Redshift (no MCP ARN)")
    print(f"credentials     : access_key={os.environ.get('AWS_ACCESS_KEY_ID', '')[:10]}...")

    results = {}

    if args.tool == "all":
        results["get_recent_articles"] = test_get_recent_articles(hours=args.hours)
        results["crawl_articles"] = test_crawl_articles(rss_only=args.rss_only)
        results["save_articles_to_redshift"] = test_save_articles_to_redshift(rss_only=args.rss_only)
        results["generate_general_themes"] = test_generate_general_themes(hours=args.hours, limit=args.limit)
        results["generate_portfolio_themes_for_client"] = test_generate_portfolio_themes_for_client(
            client_id=args.client_id, hours=args.hours
        )
    elif args.tool == "generate_portfolio_themes_for_client":
        results[args.tool] = test_generate_portfolio_themes_for_client(client_id=args.client_id, hours=args.hours)
    elif args.tool in ("crawl_articles", "save_articles_to_redshift"):
        results[args.tool] = TOOL_MAP[args.tool](rss_only=args.rss_only)
    elif args.tool in ("get_recent_articles", "generate_general_themes"):
        results[args.tool] = TOOL_MAP[args.tool](hours=args.hours)
    else:
        results[args.tool] = TOOL_MAP[args.tool]()

    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    for tool, ok in results.items():
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {status}  {tool}")
    print()

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
