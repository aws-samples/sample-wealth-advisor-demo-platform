# Market Intelligence Chat Agent

A Strands Agent for natural language stock analysis and market insights, integrated with the market_events_coordinator agent.

## Overview

The Market Intelligence Chat agent provides a conversational interface for:
- Stock quotes and historical data (Yahoo Finance)
- Multi-stock comparison and analysis
- Market themes and news context (via market_events_coordinator)
- AI-powered insights (AWS Bedrock Claude)
- Portfolio-specific analysis

## Quick Start

```bash
# Install dependencies
pnpm install

# Run tests
pnpm nx run wealth_management_portal.market_intelligence_chat:test

# Start agent locally
pnpm nx run wealth_management_portal.market_intelligence_chat:chat-agent-serve
```

## Features

### Natural Language Query Parsing
Parse complex stock queries like:
- "Compare AAPL vs MSFT over last month"
- "Analyze Tesla performance"
- "How is my portfolio performing?"
- "What's the trend for semiconductor stocks?"

### Real-Time Stock Data
- Live stock quotes from Yahoo Finance
- Historical data (1D to MAX)
- Multi-stock comparison
- Performance metrics

### Market Context Integration
- Calls market_events_coordinator agent for themes
- General market themes
- Portfolio-specific themes
- News and sentiment analysis

### AI-Powered Insights
- Professional financial analysis
- Context-aware responses
- Actionable recommendations
- 2-3 paragraph summaries

## Agent Tools

1. `parse_stock_query` - Parse natural language queries
2. `get_stock_quote` - Get real-time stock quote
3. `compare_stocks` - Compare multiple stocks
4. `analyze_stock` - Detailed single stock analysis
5. `get_related_themes` - Get market themes (calls coordinator agent)
6. `generate_ai_response` - AI-powered insights

## Example Usage

```python
# Compare stocks with market context
parsed = parse_stock_query("Compare AAPL vs MSFT")
comparison = compare_stocks(["AAPL", "MSFT"], time_range="1M")
themes = get_related_themes(tickers=["AAPL", "MSFT"], limit=5)
response = generate_ai_response(
    query="Compare AAPL vs MSFT",
    stock_data=comparison,
    themes=themes["themes"]
)
```

## Documentation

- [USAGE.md](./USAGE.md) - Comprehensive usage guide
- [CHAT_AGENT_COMPLETE.md](../CHAT_AGENT_COMPLETE.md) - Implementation details
- [MIGRATION_STATUS.md](../MIGRATION_STATUS.md) - Migration history

## Architecture

```
Chat Agent → market_events_coordinator Agent → Redshift
     ↓
Yahoo Finance (stock data)
     ↓
AWS Bedrock (AI insights)
```

## Configuration

```bash
AWS_PROFILE=wealth_management
AWS_REGION=us-west-2
REDSHIFT_WORKGROUP=financial-advisor-wg
REDSHIFT_DATABASE=financial-advisor-db
BEDROCK_REGION=us-east-1
```

## Testing

```bash
# Run all tests
pnpm nx run wealth_management_portal.market_intelligence_chat:test

# Run linting
pnpm nx run wealth_management_portal.market_intelligence_chat:lint

# Format code
pnpm nx run wealth_management_portal.market_intelligence_chat:format
```

## Dependencies

- `yfinance` - Yahoo Finance API
- `pandas` - Data manipulation
- `numpy` - Numerical operations
- `boto3` - AWS SDK
- `wealth_management_portal.common_market_events` - Shared models
- `wealth_management_portal.market_events_coordinator` - Theme agent

## Development

```bash
# Add new dependency
pnpm nx run wealth_management_portal.market_intelligence_chat:add <package-name>

# Build package
pnpm nx run wealth_management_portal.market_intelligence_chat:build

# Build Docker image
pnpm nx run wealth_management_portal.market_intelligence_chat:docker
```

## License

Proprietary
