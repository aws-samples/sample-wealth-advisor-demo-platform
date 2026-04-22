# wealth_management_portal.web_crawler

MCP server that crawls financial news from RSS feeds, saves articles to Redshift, and generates AI-powered market themes using Amazon Bedrock.

![alt text](../../images/market_intelligence.png)

## Architecture

```
RSS Feeds
    │
    ▼
MarketIntelligenceCrawler ──► Portfolio Data MCP (Redshift)
    │                              ▲
    ▼                              │
ThemeProcessor ──► Bedrock (Claude) ─┘
```

The server exposes MCP tools that:
1. Crawl articles from configurable financial RSS feeds
2. Deduplicate against existing articles in Redshift via the Portfolio Data MCP server
3. Generate general market themes and per-client portfolio themes using Bedrock Claude
4. Save everything back to Redshift via Portfolio Data MCP

## MCP Tools

| Tool | Description |
|------|-------------|
| `crawl_articles` | Crawl RSS feeds and return statistics (dry run, no save) |
| `save_articles_to_redshift` | Crawl and save new articles to Redshift |
| `get_recent_articles` | Retrieve recent articles from Redshift |
| `generate_general_themes` | Generate market-wide themes from recent articles |
| `generate_portfolio_themes_for_client` | Generate per-stock themes for a single client's top holdings |
| `generate_portfolio_themes_for_all_clients` | Batch generate portfolio themes for all active clients |

## Theme Processing Pipeline

### General Market Themes

1. Retrieve recent articles from Redshift (configurable lookback window)
2. Identify 5–6 major themes using Bedrock Claude
3. Rank themes by importance score (0–100) based on:
   - Article count (30%), source diversity (25%), recency (25%), keyword impact (20%)
4. Generate professional 2–3 sentence summaries per theme
5. Save themes and article associations to Redshift

### Portfolio Themes (per client)

1. Fetch the client's top N holdings by AUM via Portfolio Data MCP
2. For each holding, score all recent articles for relevance to that stock/ETF using Bedrock Claude
3. Identify stock-specific themes from relevant articles (minimum 2 articles per theme)
4. Rank by importance score, generate summaries, and save to Redshift
5. All tickers are processed concurrently for performance

## Project Structure

```
wealth_management_portal_web_crawler/
├── web_crawler_mcp/
│   ├── server.py              # FastMCP server with tool definitions
│   ├── crawler.py             # MarketIntelligenceCrawler (RSS fetching, dedup)
│   ├── theme_generator.py     # ThemeProcessor + PortfolioThemeProcessor (Bedrock)
│   ├── mcp_client_helper.py   # Portfolio Data MCP client utilities
│   ├── http.py                # HTTP entry point (uvicorn + decompression middleware)
│   ├── stdio.py               # stdio entry point
│   └── Dockerfile             # ARM64 container image
└── __init__.py
```

## Running

### HTTP (production / AgentCore Gateway)

```bash
pnpm nx web-crawler-mcp-serve wealth_management_portal.web_crawler
```

### stdio (local / MCP Inspector)

```bash
pnpm nx web-crawler-mcp-serve-stdio wealth_management_portal.web_crawler
```

### MCP Inspector

```bash
pnpm nx web-crawler-mcp-inspect wealth_management_portal.web_crawler
```

### Docker

```bash
pnpm nx web-crawler-mcp-docker wealth_management_portal.web_crawler
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PORTFOLIO_GATEWAY_URL` | Yes | Portfolio Data MCP server URL (SigV4-authenticated) |
| `AWS_REGION` | No | AWS region (default: `us-east-1`) |
| `FEED_CONNECT_TIMEOUT` | No | RSS feed connection timeout in seconds (default: `5`) |
| `FEED_READ_TIMEOUT` | No | RSS feed read timeout in seconds (default: `10`) |

## Typical Workflow

```
1. save_articles_to_redshift()           # Crawl & persist articles
2. generate_general_themes(hours=48)     # Market-wide themes
3. generate_portfolio_themes_for_all_clients()  # Per-client themes
```

This workflow runs daily via EventBridge Scheduler → Step Functions.

## Testing

```bash
pnpm nx test wealth_management_portal.web_crawler
```

## Dependencies

- `feedparser` / `beautifulsoup4` / `newspaper3k` — RSS parsing and article extraction
- `mcp` (1.26.0) — MCP server SDK
- `strands-agents` — MCP client for Portfolio Data access
- `boto3` — Bedrock (theme generation) and SigV4 auth
- `wealth_management_portal.common_market_events` — Shared Article/Theme models
- `wealth_management_portal.common_auth` — SigV4 HTTP auth
