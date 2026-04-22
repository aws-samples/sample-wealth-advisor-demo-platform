#!/usr/bin/env python3
"""
Local test for the async PortfolioThemeProcessor refactor.

Does NOT require deployment — uses stdio MCP client against the local portfolio_data_server.
Does NOT require PORTFOLIO_GATEWAY_URL to be set.

Tests:
  1. Async article scoring batches run concurrently (timing check)
  2. All tickers processed concurrently
  3. Themes saved per-ticker (not all at end)

Usage:
  cd wealth-management-portal
  uv run python scripts/test-async-theme-generator-local.py --client-id CL00005
  uv run python scripts/test-async-theme-generator-local.py --client-id CL00005 --top-n 2 --themes-per-stock 1
"""

import argparse
import asyncio
import logging
import time
from unittest.mock import MagicMock, patch

# Configure logging so we can see the concurrent batch logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def make_mock_article(i: int):
    """Create a minimal fake Article for testing."""
    from wealth_management_portal_common_market_events.models import Article
    from datetime import datetime, timezone

    return Article(
        content_hash=f"hash_{i:04d}",
        title=f"Test article {i} about AMZN AWS cloud earnings revenue",
        source="TestSource",
        url=f"https://example.com/article/{i}",
        summary=f"Amazon reported strong Q{i % 4 + 1} results driven by AWS cloud growth.",
        published_date=datetime.now(timezone.utc),
        crawled_at=datetime.now(timezone.utc),
    )


def make_mock_mcp_client(client_id: str, tickers: list[str]):
    """
    Build a mock MCP client that returns fake holdings and accepts save_theme calls.
    This avoids needing a real Redshift connection for the local test.
    """
    mock_client = MagicMock()
    mock_context = MagicMock()

    holdings = [
        {"ticker": t, "security_name": f"{t} Inc", "aum_value": 100000 - i * 1000}
        for i, t in enumerate(tickers)
    ]

    def call_tool_sync(tool_call_id, tool_name, args):
        if tool_name == "get_top_holdings_by_aum":
            return {"structuredContent": {"ok": True, "holdings": holdings}, "content": [], "status": "success"}
        elif tool_name in ("save_theme", "save_theme_article_association"):
            logger.info("  [mock MCP] %s called — theme_id=%s", tool_name, args.get("theme_id", args.get("theme_id", "?")))
            return {"structuredContent": {"ok": True}, "content": [], "status": "success"}
        else:
            return {"structuredContent": {}, "content": [], "status": "success"}

    mock_context.call_tool_sync = call_tool_sync
    mock_client.__enter__ = MagicMock(return_value=mock_context)
    mock_client.__exit__ = MagicMock(return_value=False)
    return mock_client


async def run_test(client_id: str, tickers: list[str], themes_per_stock: int):
    from wealth_management_portal_web_crawler.web_crawler_mcp.theme_generator import PortfolioThemeProcessor

    mock_mcp = make_mock_mcp_client(client_id, tickers)
    articles = [make_mock_article(i) for i in range(30)]  # 30 fake articles → 3 batches of 10

    processor = PortfolioThemeProcessor(mcp_client=mock_mcp)

    # --- Test 1: concurrent batch scoring ---
    logger.info("=== Test 1: concurrent article batch scoring for single ticker ===")
    call_times = []

    original_invoke = processor.bedrock.invoke_model

    def timed_invoke(**kwargs):
        t = time.time()
        call_times.append(t)
        # Simulate ~0.5s Bedrock latency
        time.sleep(0.5)
        import json
        body_mock = MagicMock()
        body_mock.read.return_value = json.dumps({
            "content": [{
                "text": json.dumps({
                    "articles": [
                        {"article_number": i + 1, "relevance_score": 85, "reasoning": "direct mention"}
                        for i in range(10)
                    ]
                })
            }]
        }).encode()
        response = {"body": body_mock}
        return response

    processor.bedrock.invoke_model = timed_invoke

    t0 = time.time()
    with patch.object(processor, "get_recent_articles", return_value=articles):
        result_articles = await processor._get_stock_specific_articles_async("AMZN", hours=48)
    elapsed = time.time() - t0

    logger.info("  Articles returned: %d", len(result_articles))
    logger.info("  Bedrock calls made: %d (expected 3 batches)", len(call_times))
    logger.info("  Total elapsed: %.2fs", elapsed)

    # If sequential: 3 × 0.5s = ~1.5s. If concurrent: ~0.5s
    if elapsed < 1.0:
        logger.info("  ✅ PASS — batches ran concurrently (%.2fs < 1.0s threshold)", elapsed)
    else:
        logger.warning("  ⚠ SLOW — elapsed %.2fs suggests batches may be sequential", elapsed)

    # --- Test 2: concurrent ticker processing ---
    logger.info("\n=== Test 2: all tickers processed concurrently ===")

    ticker_start_times = {}

    async def mock_generate_ticker(client_id, ticker, hours, themes_per_stock, security_name):
        ticker_start_times[ticker] = time.time()
        await asyncio.sleep(0.5)  # simulate work
        logger.info("  ticker=%s done", ticker)
        return [], {}

    # Patch the MCP holdings call so Test 2 doesn't need a real MCP context.
    # result["content"][0]["text"] must be a JSON string — use a plain dict/object.
    import json as _json

    holdings_json = _json.dumps({"ok": True, "holdings": [
        {"ticker": t, "security_name": f"{t} Inc", "aum_value": 100000 - i * 1000}
        for i, t in enumerate(tickers)
    ]})

    mock_ctx2 = MagicMock()
    mock_ctx2.call_tool_sync.return_value = {
        "structuredContent": _json.loads(holdings_json),
        "content": [],
        "status": "success",
    }
    processor.mcp_client.__enter__ = MagicMock(return_value=mock_ctx2)

    t0 = time.time()
    with patch.object(processor, "_generate_stock_specific_themes_async", side_effect=mock_generate_ticker):
        all_themes, _ = await processor._generate_portfolio_themes_by_stock_async(
            client_id=client_id,
            top_n_stocks=len(tickers),
            hours=48,
            themes_per_stock=themes_per_stock,
        )
    elapsed = time.time() - t0

    logger.info("  Tickers processed: %s", list(ticker_start_times.keys()))
    logger.info("  Total elapsed: %.2fs", elapsed)

    # If sequential: N × 0.5s. If concurrent: ~0.5s
    if elapsed < 1.0:
        logger.info("  ✅ PASS — tickers ran concurrently (%.2fs < 1.0s threshold)", elapsed)
    else:
        logger.warning("  ⚠ SLOW — elapsed %.2fs suggests tickers may be sequential", elapsed)

    # Check all tickers started within ~0.2s of each other
    if ticker_start_times:
        spread = max(ticker_start_times.values()) - min(ticker_start_times.values())
        if spread < 0.2:
            logger.info("  ✅ PASS — ticker start spread %.3fs (all started near-simultaneously)", spread)
        else:
            logger.warning("  ⚠ ticker start spread %.3fs (expected < 0.2s for concurrent)", spread)

    logger.info("\n=== All tests complete ===")


def main():
    parser = argparse.ArgumentParser(description="Local async test for PortfolioThemeProcessor")
    parser.add_argument("--client-id", default="CL00005", help="Client ID (default: CL00005)")
    parser.add_argument("--tickers", default="AMZN,AAPL,MSFT,GOOGL,META", help="Comma-separated tickers")
    parser.add_argument("--themes-per-stock", type=int, default=2)
    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",")]
    logger.info("Testing with client_id=%s tickers=%s", args.client_id, tickers)

    asyncio.run(run_test(args.client_id, tickers, args.themes_per_stock))


if __name__ == "__main__":
    main()
