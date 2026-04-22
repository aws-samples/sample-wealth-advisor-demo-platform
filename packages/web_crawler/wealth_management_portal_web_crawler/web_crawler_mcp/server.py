import logging
import os

from mcp.server.fastmcp import FastMCP

from wealth_management_portal_web_crawler.web_crawler_mcp.crawler import (
    MarketIntelligenceCrawler,
)
from wealth_management_portal_web_crawler.web_crawler_mcp.mcp_client_helper import (
    build_tool_name_map,
    extract_mcp_data,
    get_portfolio_mcp_client,
)
from wealth_management_portal_web_crawler.web_crawler_mcp.theme_generator import (
    PortfolioThemeProcessor,
    ThemeProcessor,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="WebCrawlerMcp",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
    stateless_http=True,
)


@mcp.tool(description="Crawl articles from RSS feeds")
def crawl_articles(
    rss_only: bool = False,
) -> dict:
    """
    Crawl articles from configured RSS feeds and check for duplicates against Redshift.

    Args:
        rss_only: If True, only use RSS content without fetching full articles (faster)

    Returns:
        Dictionary with crawl statistics and article count
    """
    print(f"[crawl_articles] START rss_only={rss_only}")
    logger.info("[crawl_articles] START rss_only=%s", rss_only)
    try:
        # Get existing article hashes from Portfolio MCP
        print("[crawl_articles] Fetching existing article hashes from Portfolio MCP...")
        logger.info("[crawl_articles] Fetching existing article hashes from Portfolio MCP")
        mcp_client = get_portfolio_mcp_client()
        with mcp_client as client:
            names = build_tool_name_map(client, ["get_existing_article_hashes"])
            result = client.call_tool_sync("get_existing_article_hashes_001", names["get_existing_article_hashes"], {})
            response = extract_mcp_data(result)

            # Portfolio MCP returns {"ok": True, "hashes": [...]}
            if response.get("ok"):
                existing_hashes = set(response.get("hashes", []))
                print(f"[crawl_articles] Got {len(existing_hashes)} existing hashes from Redshift")
                logger.info("[crawl_articles] Got %d existing hashes from Redshift", len(existing_hashes))
            else:
                logger.error("[crawl_articles] Failed to get existing hashes: %s", response.get("error"))
                return {"success": False, "error": response.get("error", "Failed to get existing hashes")}

        # Initialize crawler with existing hashes
        print(f"[crawl_articles] Initializing crawler (rss_only={rss_only})...")
        logger.info("[crawl_articles] Initializing MarketIntelligenceCrawler")
        crawler = MarketIntelligenceCrawler(rss_only=rss_only, existing_hashes=existing_hashes)

        # Crawl all sources
        print("[crawl_articles] Crawling all sources...")
        logger.info("[crawl_articles] Starting crawl_all_sources")
        articles, stats = crawler.crawl_all_sources()

        logger.info(
            "[crawl_articles] Crawl complete: articles=%d duplicates=%d errors=%d",
            len(articles),
            stats.duplicates,
            stats.errors,
        )

        return {
            "success": True,
            "articles_found": len(articles),
            "total_crawled": stats.total_crawled,
            "new_articles": stats.new_articles,
            "duplicates": stats.duplicates,
            "errors": stats.errors,
            "sources": stats.sources,
            "message": f"Successfully crawled {len(articles)} new articles",
        }

    except Exception as e:
        print(f"[crawl_articles] ERROR: {e}")
        logger.exception("[crawl_articles] Unexpected error")
        return {"success": False, "error": str(e), "message": f"Crawl failed: {str(e)}"}


@mcp.tool(description="Save crawled articles to Redshift")
def save_articles_to_redshift(
    rss_only: bool = False,
    max_sources: int | None = None,
) -> dict:
    """
    Crawl articles and save them directly to Redshift via Portfolio MCP.

    Args:
        rss_only: If True, only use RSS content without fetching full articles
        max_sources: If set, limit crawling to the first N sources (useful for testing)

    Returns:
        Dictionary with operation results and statistics
    """
    print(f"[save_articles_to_redshift] START rss_only={rss_only} max_sources={max_sources}")
    logger.info("[save_articles_to_redshift] START rss_only=%s max_sources=%s", rss_only, max_sources)
    try:
        # Get Portfolio MCP client
        mcp_client = get_portfolio_mcp_client()

        # Get existing URLs for deduplication
        print("[save_articles_to_redshift] Fetching existing article URLs...")
        logger.info("[save_articles_to_redshift] Fetching existing article URLs from Portfolio MCP")
        with mcp_client as client:
            names = build_tool_name_map(client, ["get_existing_article_urls"])
            result = client.call_tool_sync("get_existing_article_urls_001", names["get_existing_article_urls"], {})
            response = extract_mcp_data(result)

            # Portfolio MCP returns {"ok": True, "urls": [...]}
            if response.get("ok"):
                existing_urls = set(response.get("urls", []))
                print(f"[save_articles_to_redshift] Got {len(existing_urls)} existing URLs")
                logger.info("[save_articles_to_redshift] Got %d existing URLs", len(existing_urls))
            else:
                logger.error("[save_articles_to_redshift] Failed to get URLs: %s", response.get("error"))
                return {"success": False, "error": response.get("error", "Failed to get existing URLs")}

        # Crawl articles
        print("[save_articles_to_redshift] Starting crawl...")
        logger.info("[save_articles_to_redshift] Initializing crawler and crawling all sources")
        crawler = MarketIntelligenceCrawler(rss_only=rss_only, existing_urls=existing_urls)
        articles, stats = crawler.crawl_all_sources(max_sources=max_sources)

        print(f"[save_articles_to_redshift] Crawl done: {len(articles)} new articles to save")
        logger.info(
            "[save_articles_to_redshift] Crawl done: new=%d duplicates=%d errors=%d",
            len(articles),
            stats.duplicates,
            stats.errors,
        )

        # Save articles to Redshift via Portfolio MCP
        saved_count = 0
        errors = []

        print(f"[save_articles_to_redshift] Saving {len(articles)} articles to Redshift via Portfolio MCP...")
        logger.info("[save_articles_to_redshift] Saving %d articles to Redshift", len(articles))
        with mcp_client as client:
            names = build_tool_name_map(client, ["save_article"])
            for article in articles:
                try:
                    # Convert article to dict for MCP call
                    article_dict = {
                        "content_hash": article.content_hash,
                        "title": article.title,
                        "url": article.url,
                        "source": article.source,
                        "published_date": article.published_date.isoformat() if article.published_date else None,
                        "summary": article.summary,
                        "content": article.content,
                        "author": article.author,
                    }

                    result = client.call_tool_sync(f"save_article_{saved_count}", names["save_article"], article_dict)
                    response = extract_mcp_data(result)
                    if not response.get("ok"):
                        raise RuntimeError(response.get("error", "save_article returned not ok"))
                    saved_count += 1
                    if saved_count % 10 == 0:
                        print(f"[save_articles_to_redshift] Saved {saved_count}/{len(articles)} articles so far...")
                        logger.info("[save_articles_to_redshift] Progress: %d/%d saved", saved_count, len(articles))
                except Exception as e:
                    errors.append(f"Failed to save article {article.content_hash}: {str(e)}")
                    logger.error("[save_articles_to_redshift] Failed to save article %s: %s", article.content_hash, e)

        print(f"[save_articles_to_redshift] DONE: saved={saved_count} save_errors={len(errors)}")
        logger.info("[save_articles_to_redshift] DONE saved=%d save_errors=%d", saved_count, len(errors))

        return {
            "success": True,
            "articles_saved": saved_count,
            "total_crawled": stats.total_crawled,
            "new_articles": stats.new_articles,
            "duplicates": stats.duplicates,
            "errors": stats.errors,
            "save_errors": errors,
            "sources": stats.sources,
            "message": f"Successfully saved {saved_count} articles to Redshift",
        }

    except Exception as e:
        print(f"[save_articles_to_redshift] ERROR: {e}")
        logger.exception("[save_articles_to_redshift] Unexpected error")
        return {"success": False, "error": str(e), "message": f"Operation failed: {str(e)}"}


@mcp.tool(description="Get recent articles from Redshift")
def get_recent_articles(
    hours: int = 48,
    limit: int = 100,
) -> dict:
    """
    Get recent articles from Redshift via Portfolio MCP.

    Args:
        hours: Number of hours to look back
        limit: Maximum number of articles to retrieve

    Returns:
        Dictionary with articles
    """
    print(f"[get_recent_articles] START hours={hours} limit={limit}")
    logger.info("[get_recent_articles] START hours=%d limit=%d", hours, limit)
    try:
        mcp_client = get_portfolio_mcp_client()
        print("[get_recent_articles] Calling Portfolio MCP get_recent_articles...")
        logger.info("[get_recent_articles] Calling Portfolio MCP get_recent_articles")
        with mcp_client as client:
            names = build_tool_name_map(client, ["get_recent_articles"])
            result = client.call_tool_sync("get_recent_articles_001", names["get_recent_articles"], {"hours": hours})
            response = extract_mcp_data(result)

            # Portfolio MCP returns {"ok": True, "articles": [...]}
            if response.get("ok"):
                articles = response.get("articles", [])
                print(f"[get_recent_articles] Got {len(articles)} articles from Portfolio MCP, returning top {limit}")
                logger.info("[get_recent_articles] Got %d articles, returning top %d", len(articles), limit)
            else:
                logger.error("[get_recent_articles] Portfolio MCP error: %s", response.get("error"))
                return {"success": False, "error": response.get("error", "Unknown error")}

        return {
            "success": True,
            "articles": articles[:limit],
            "count": len(articles[:limit]),
            "message": f"Retrieved {len(articles[:limit])} recent articles",
        }

    except Exception as e:
        print(f"[get_recent_articles] ERROR: {e}")
        logger.exception("[get_recent_articles] Unexpected error")
        return {"success": False, "error": str(e), "message": f"Failed to get articles: {str(e)}"}


@mcp.tool(description="Generate general market themes from recent articles")
def generate_general_themes(
    hours: int = 48,
    limit: int = 6,
) -> dict:
    """
    Generate general market themes from recent articles.

    This should be called after crawling and saving articles.
    Generates themes and saves them to Redshift via Portfolio MCP.

    Args:
        hours: Look back period in hours for articles
        limit: Maximum number of themes to generate

    Returns:
        Dict with success status and themes generated
    """
    print(f"[generate_general_themes] START hours={hours} limit={limit}")
    logger.info("[generate_general_themes] START hours=%d limit=%d", hours, limit)
    try:
        # Get Portfolio MCP client
        print("[generate_general_themes] Initializing ThemeProcessor...")
        logger.info("[generate_general_themes] Initializing ThemeProcessor with bedrock_region=us-east-1")
        mcp_client = get_portfolio_mcp_client()

        processor = ThemeProcessor(
            mcp_client=mcp_client,
            bedrock_region="us-east-1",
            use_cross_region=True,
        )

        # Generate themes
        print(f"[generate_general_themes] Running process_themes (hours={hours}, limit={limit})...")
        logger.info("[generate_general_themes] Calling process_themes")
        themes, theme_articles_map = processor.process_themes(hours=hours, limit=limit)

        print(f"[generate_general_themes] process_themes returned {len(themes)} themes")
        logger.info("[generate_general_themes] process_themes returned %d themes", len(themes))

        # Save to Redshift via Portfolio MCP
        print(f"[generate_general_themes] Saving {len(themes)} themes to Redshift...")
        logger.info("[generate_general_themes] Saving themes to Redshift via Portfolio MCP")
        processor.save_themes_to_redshift(themes, theme_articles_map)

        print(f"[generate_general_themes] DONE: {len(themes)} themes saved successfully")
        logger.info("[generate_general_themes] DONE: %d themes saved", len(themes))

        return {
            "success": True,
            "themes_generated": len(themes),
            "themes": [
                {
                    "theme_id": theme.theme_id,
                    "title": theme.title,
                    "sentiment": theme.sentiment,
                    "score": theme.score,
                    "article_count": theme.article_count,
                }
                for theme in themes
            ],
            "message": f"Successfully generated {len(themes)} general market themes",
        }
    except Exception as e:
        print(f"[generate_general_themes] ERROR: {e}")
        logger.exception("[generate_general_themes] Unexpected error")
        return {"success": False, "error": str(e), "message": f"Theme generation failed: {str(e)}"}


@mcp.tool(description="Generate portfolio themes for all active clients")
def generate_portfolio_themes_for_all_clients(
    top_n_stocks: int = 5,
    themes_per_stock: int = 3,
    hours: int = 48,
) -> dict:
    """
    Generate portfolio-specific themes for all active clients using per-stock generation.

    Fetches all clients from Redshift and generates themes for top N stocks in each portfolio.

    Args:
        top_n_stocks: Number of top holdings by AUM to generate themes for (default: 5)
        themes_per_stock: Number of themes to generate per stock (default: 3)
        hours: Look back period in hours for articles

    Returns:
        Dict with success status and count of clients processed
    """
    print(
        f"[generate_portfolio_themes_for_all_clients] START"
        f" top_n_stocks={top_n_stocks} themes_per_stock={themes_per_stock} hours={hours}"
    )
    logger.info(
        "[generate_portfolio_themes_for_all_clients] START top_n_stocks=%d themes_per_stock=%d hours=%d",
        top_n_stocks,
        themes_per_stock,
        hours,
    )
    try:
        # Get Portfolio MCP client
        mcp_client = get_portfolio_mcp_client()

        processor = PortfolioThemeProcessor(
            mcp_client=mcp_client,
            bedrock_region="us-east-1",
            use_cross_region=True,
        )

        # Get all active clients via Portfolio MCP
        print("[generate_portfolio_themes_for_all_clients] Fetching active clients from Portfolio MCP...")
        logger.info("[generate_portfolio_themes_for_all_clients] Fetching active clients")
        with mcp_client as client:
            names = build_tool_name_map(client, ["get_active_clients"])
            result = client.call_tool_sync("get_active_clients_001", names["get_active_clients"], {})
            response = extract_mcp_data(result)

            # Portfolio MCP returns {"ok": True, "client_ids": [...]}
            if response.get("ok"):
                client_ids = response.get("client_ids", [])
                print(f"[generate_portfolio_themes_for_all_clients] Found {len(client_ids)} active clients")
                logger.info("[generate_portfolio_themes_for_all_clients] Found %d active clients", len(client_ids))
            else:
                logger.error(
                    "[generate_portfolio_themes_for_all_clients] Failed to get clients: %s", response.get("error")
                )
                return {"success": False, "error": response.get("error", "Failed to get active clients")}

        if not client_ids:
            print("[generate_portfolio_themes_for_all_clients] No active clients found, exiting")
            return {"success": True, "clients_processed": 0, "message": "No active clients found"}

        # Generate themes for each client
        results = []
        for i, client_id in enumerate(client_ids, 1):
            print(f"[generate_portfolio_themes_for_all_clients] Processing client {i}/{len(client_ids)}: {client_id}")
            logger.info(
                "[generate_portfolio_themes_for_all_clients] Processing client %d/%d: %s",
                i,
                len(client_ids),
                client_id,
            )
            try:
                # Generate per-stock themes (saved to Redshift per-ticker as they complete)
                themes, theme_articles_map = processor.process_portfolio_themes(
                    client_id=client_id,
                    top_n_stocks=top_n_stocks,
                    themes_per_stock=themes_per_stock,
                    hours=hours,
                )

                # Themes already saved to Redshift per-ticker during generation

                # Count themes by stock
                stocks_with_themes = len(set(t.ticker for t in themes if t.ticker))

                print(
                    f"[generate_portfolio_themes_for_all_clients]"
                    f" Client {client_id}: {len(themes)} themes across {stocks_with_themes} stocks"
                )
                logger.info(
                    "[generate_portfolio_themes_for_all_clients] Client %s: themes=%d stocks=%d",
                    client_id,
                    len(themes),
                    stocks_with_themes,
                )

                results.append(
                    {
                        "client_id": client_id,
                        "status": "success",
                        "themes_generated": len(themes),
                        "stocks_covered": stocks_with_themes,
                    }
                )
            except Exception as e:
                print(f"[generate_portfolio_themes_for_all_clients] ERROR for client {client_id}: {e}")
                logger.exception("[generate_portfolio_themes_for_all_clients] Error for client %s", client_id)
                results.append({"client_id": client_id, "status": "error", "error": str(e)})

        successful = sum(1 for r in results if r["status"] == "success")
        print(f"[generate_portfolio_themes_for_all_clients] DONE: {successful}/{len(client_ids)} clients successful")
        logger.info(
            "[generate_portfolio_themes_for_all_clients] DONE: successful=%d total=%d",
            successful,
            len(client_ids),
        )
        return {
            "success": True,
            "clients_processed": len(client_ids),
            "successful": successful,
            "results": results,
            "message": f"Processed {len(client_ids)} clients, {successful} successful",
        }
    except Exception as e:
        print(f"[generate_portfolio_themes_for_all_clients] ERROR: {e}")
        logger.exception("[generate_portfolio_themes_for_all_clients] Unexpected error")
        return {"success": False, "error": str(e), "message": f"Batch processing failed: {str(e)}"}


@mcp.tool(description="Generate portfolio themes for a single client")
def generate_portfolio_themes_for_client(
    client_id: str,
    top_n_stocks: int = 5,
    themes_per_stock: int = 3,
    hours: int = 48,
) -> dict:
    """
    Generate portfolio-specific themes for a single client using per-stock generation.

    Args:
        client_id: Client identifier (e.g., "CL00014")
        top_n_stocks: Number of top holdings by AUM to generate themes for (default: 5)
        themes_per_stock: Number of themes to generate per stock (default: 3)
        hours: Look back period in hours for articles

    Returns:
        Dict with success status and themes generated
    """
    print(
        f"[generate_portfolio_themes_for_client] START client_id={client_id}"
        f" top_n_stocks={top_n_stocks} themes_per_stock={themes_per_stock} hours={hours}"
    )
    logger.info(
        "[generate_portfolio_themes_for_client] START client_id=%s top_n_stocks=%d themes_per_stock=%d hours=%d",
        client_id,
        top_n_stocks,
        themes_per_stock,
        hours,
    )
    try:
        # Get Portfolio MCP client
        mcp_client = get_portfolio_mcp_client()

        processor = PortfolioThemeProcessor(
            mcp_client=mcp_client,
            bedrock_region="us-east-1",
            use_cross_region=True,
        )

        # Get top holdings via Portfolio MCP
        print(f"[generate_portfolio_themes_for_client] Fetching top {top_n_stocks} holdings for {client_id}...")
        logger.info("[generate_portfolio_themes_for_client] Fetching top holdings for client %s", client_id)
        with mcp_client as client:
            names = build_tool_name_map(client, ["get_top_holdings_by_aum"])
            result = client.call_tool_sync(
                "get_top_holdings_001",
                names["get_top_holdings_by_aum"],
                {"client_id": client_id, "limit": top_n_stocks},
            )
            response = extract_mcp_data(result)

            # Portfolio MCP returns {"ok": True, "holdings": [...]}
            if response.get("ok"):
                top_holdings = response.get("holdings", [])
                tickers = [h.get("ticker") for h in top_holdings]
                print(f"[generate_portfolio_themes_for_client] Top holdings for {client_id}: {tickers}")
                logger.info("[generate_portfolio_themes_for_client] Top holdings for %s: %s", client_id, tickers)
            else:
                logger.error("[generate_portfolio_themes_for_client] Failed to get holdings: %s", response.get("error"))
                return {
                    "success": False,
                    "error": response.get("error", f"No holdings found for client {client_id}"),
                }

        if not top_holdings:
            print(f"[generate_portfolio_themes_for_client] No holdings found for {client_id}")
            return {
                "success": False,
                "error": f"No holdings found for client {client_id}",
            }

        # Generate per-stock themes (themes are saved to Redshift per-ticker as they complete)
        print(f"[generate_portfolio_themes_for_client] Running process_portfolio_themes for {client_id}...")
        logger.info("[generate_portfolio_themes_for_client] Running process_portfolio_themes for %s", client_id)
        themes, theme_articles_map = processor.process_portfolio_themes(
            client_id=client_id,
            top_n_stocks=top_n_stocks,
            themes_per_stock=themes_per_stock,
            hours=hours,
        )

        print(f"[generate_portfolio_themes_for_client] Generated {len(themes)} themes for {client_id}")
        logger.info("[generate_portfolio_themes_for_client] Generated %d themes for %s", len(themes), client_id)

        # Themes already saved to Redshift per-ticker during generation

        # Group themes by stock
        themes_by_stock = {}
        for theme in themes:
            if theme.ticker:
                if theme.ticker not in themes_by_stock:
                    themes_by_stock[theme.ticker] = []
                themes_by_stock[theme.ticker].append(
                    {
                        "theme_id": theme.theme_id,
                        "title": theme.title,
                        "sentiment": theme.sentiment,
                        "score": theme.score,
                        "article_count": theme.article_count,
                    }
                )

        print(
            f"[generate_portfolio_themes_for_client] DONE:"
            f" {len(themes)} themes across {len(themes_by_stock)} stocks for {client_id}"
        )
        logger.info(
            "[generate_portfolio_themes_for_client] DONE: client=%s themes=%d stocks=%d",
            client_id,
            len(themes),
            len(themes_by_stock),
        )

        return {
            "success": True,
            "client_id": client_id,
            "top_holdings": [{"ticker": h["ticker"], "aum": h["aum_value"]} for h in top_holdings],
            "themes_generated": len(themes),
            "stocks_covered": len(themes_by_stock),
            "themes_by_stock": themes_by_stock,
            "message": (
                f"Successfully generated {len(themes)} themes across {len(themes_by_stock)} stocks for {client_id}"
            ),
        }
    except Exception as e:
        print(f"[generate_portfolio_themes_for_client] ERROR client={client_id}: {e}")
        logger.exception("[generate_portfolio_themes_for_client] Unexpected error for client %s", client_id)
        return {"success": False, "error": str(e), "message": f"Theme generation failed: {str(e)}"}


@mcp.resource("crawler://guidance", description="Web Crawler Usage Guide")
def crawler_guidance() -> str:
    return """## Web Crawler MCP Server

This MCP server provides tools for crawling financial news articles from RSS feeds and generating market themes.

### Available Tools

#### Article Crawling

1. **crawl_articles**: Crawl articles from RSS feeds and check for duplicates
   - Returns statistics without saving to database
   - Use `rss_only=True` for faster crawling (uses RSS summaries only)

2. **save_articles_to_redshift**: Crawl and save articles directly to Redshift
   - Automatically checks for duplicates
   - Saves crawl log for tracking
   - Use `rss_only=True` for faster crawling

3. **get_crawl_stats**: Get recent crawl statistics from Redshift
   - View historical crawl performance
   - Track articles over time

#### Theme Generation

4. **generate_general_themes**: Generate general market themes from recent articles
   - Analyzes articles from last N hours
   - Generates 5-6 major market themes
   - Saves themes to Redshift

5. **generate_portfolio_themes_for_all_clients**: Generate portfolio themes for all active clients
   - Processes all clients in batch
   - Generates per-stock themes for top N holdings by AUM
   - Default: top 5 stocks, 3 themes per stock
   - Saves all themes to Redshift

6. **generate_portfolio_themes_for_client**: Generate portfolio themes for a single client
   - Generates themes for top N stocks in client's portfolio
   - Themes are stock-specific, not portfolio-wide
   - Default: top 5 stocks by AUM, 3 themes per stock
   - Saves themes to Redshift

### News Sources

The crawler monitors 13 working RSS feeds:
- Wall Street Journal, Financial Times, CNBC, MarketWatch, Yahoo Finance
- Benzinga, Motley Fool, Insider Monkey
- The Economist, Fortune
- CoinDesk, Crypto News, U.S. News Money

### Typical Workflow

```python
# Step 1: Crawl and save articles
result = save_articles_to_redshift(rss_only=False)

# Step 2: Generate general market themes
themes = generate_general_themes(hours=48, limit=6)

# Step 3: Generate portfolio themes for all clients
portfolio_themes = generate_portfolio_themes_for_all_clients(
    top_n_stocks=5,  # Top 5 holdings by AUM
    themes_per_stock=3,  # 3 themes per stock
    hours=48
)

# Or generate for specific client
client_themes = generate_portfolio_themes_for_client(
    client_id="CL00014",
    top_n_stocks=5,
    themes_per_stock=3,
    hours=48
)
```
"""
