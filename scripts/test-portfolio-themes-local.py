#!/usr/bin/env python3
"""
Test portfolio theme generation locally — no deployment needed.
Uses stdio MCP client against local portfolio_data_server (requires SSM tunnel on localhost:5439).

Usage:
  cd wealth-management-portal
  uv run python scripts/test-portfolio-themes-local.py --client-id CL00001
  uv run python scripts/test-portfolio-themes-local.py --client-id CL00001 --top-n 2 --themes-per-stock 1
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

# Force stdio mode — no Gateway URL needed
os.environ.pop("PORTFOLIO_GATEWAY_URL", None)

from wealth_management_portal_web_crawler.web_crawler_mcp.theme_generator import PortfolioThemeProcessor
from wealth_management_portal_web_crawler.web_crawler_mcp.mcp_client_helper import get_portfolio_mcp_client, extract_mcp_data


def main():
    parser = argparse.ArgumentParser(description="Test portfolio theme generation locally")
    parser.add_argument("--client-id", required=True, help="Client ID e.g. CL00001")
    parser.add_argument("--top-n", type=int, default=3, help="Top N stocks (default: 3)")
    parser.add_argument("--themes-per-stock", type=int, default=2, help="Themes per stock (default: 2)")
    parser.add_argument("--hours", type=int, default=48, help="Lookback hours (default: 48)")
    args = parser.parse_args()

    print(f"[local] client_id={args.client_id} top_n={args.top_n} themes_per_stock={args.themes_per_stock} hours={args.hours}")

    mcp_client = get_portfolio_mcp_client()
    processor = PortfolioThemeProcessor(
        mcp_client=mcp_client,
        bedrock_region="us-east-1",
        use_cross_region=True,
    )

    # Step 1: check articles available
    print("\n[local] Fetching recent articles...")
    articles = processor.get_recent_articles(hours=args.hours)
    print(f"[local] Found {len(articles)} articles in last {args.hours}h")
    if len(articles) < 3:
        print(f"[local] ERROR: need at least 3 articles, found {len(articles)}")
        sys.exit(1)

    # Step 2: generate and save portfolio themes
    print(f"\n[local] Generating portfolio themes for {args.client_id}...")
    themes, theme_articles_map = processor.process_portfolio_themes(
        client_id=args.client_id,
        top_n_stocks=args.top_n,
        themes_per_stock=args.themes_per_stock,
        hours=args.hours,
    )

    print(f"\n[local] Generated {len(themes)} themes across {len(set(t.ticker for t in themes if t.ticker))} stocks:")
    for t in sorted(themes, key=lambda x: (x.ticker or "", x.rank)):
        print(f"  ticker={t.ticker} rank={t.rank} score={t.score:.2f} [{t.sentiment}] {t.title[:70]}")

    # Step 3: verify themes were saved by reading them back
    print(f"\n[local] Verifying themes saved to Redshift...")
    with get_portfolio_mcp_client() as client:
        result = client.call_tool_sync("verify_themes_001", "get_client_report_data", {"client_id": args.client_id})
        data = extract_mcp_data(result)
        saved_themes = data.get("themes", [])
        portfolio_themes = [t for t in saved_themes if t.get("client_id") == args.client_id and t.get("ticker")]
        print(f"[local] Found {len(portfolio_themes)} portfolio themes in Redshift for {args.client_id}")
        for t in portfolio_themes[:5]:
            print(f"  ticker={t.get('ticker')} rank={t.get('rank')} {t.get('title', '')[:70]}")

    print(f"\n[local] Done.")


if __name__ == "__main__":
    main()
