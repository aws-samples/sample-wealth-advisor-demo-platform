from contextlib import contextmanager

import boto3
from botocore.config import Config
from strands import Agent, tool
from strands_tools import current_time

from wealth_management_portal_market_intelligence_chat.query_parser import QueryParser
from wealth_management_portal_market_intelligence_chat.stock_service import StockDataService

# Initialize services
stock_service = StockDataService()
query_parser = QueryParser()


@tool
def parse_stock_query(query: str, portfolio_tickers: list[str] | None = None) -> dict:
    """
    Parse natural language stock query into structured data.

    Args:
        query: User's natural language query about stocks
        portfolio_tickers: Optional list of portfolio tickers for context

    Returns:
        Dictionary with parsed query details (intent, tickers, time_range, etc.)
    """
    try:
        parsed = query_parser.parse_query(query, portfolio_tickers)

        return {
            "success": True,
            "intent": parsed.intent,
            "tickers": parsed.tickers,
            "time_range": parsed.time_range,
            "comparison_type": parsed.comparison_type,
            "context": parsed.context,
            "confidence": parsed.confidence,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "message": f"Failed to parse query: {str(e)}"}


@tool
def get_stock_quote(symbol: str) -> dict:
    """
    Get real-time stock quote for a single stock.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')

    Returns:
        Dictionary with current stock quote data
    """
    try:
        quote = stock_service.get_stock_quote(symbol)

        if not quote:
            return {"success": False, "error": "Stock not found", "message": f"Could not find data for {symbol}"}

        return {
            "success": True,
            "symbol": quote.symbol,
            "name": quote.name,
            "price": quote.price,
            "change": quote.change,
            "change_percent": quote.change_percent,
            "prev_close": quote.prev_close,
            "open": quote.open,
            "high": quote.high,
            "low": quote.low,
            "volume": quote.volume,
            "market_cap": quote.market_cap,
            "sector": quote.sector,
            "industry": quote.industry,
            "updated_at": quote.updated_at,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "message": f"Failed to get quote for {symbol}: {str(e)}"}


@tool
def compare_stocks(symbols: list[str], time_range: str = "1M") -> dict:
    """
    Compare multiple stocks with historical performance data.

    Args:
        symbols: List of stock ticker symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])
        time_range: Time period (1D, 5D, 1M, 6M, YTD, 1Y, 5Y, MAX)

    Returns:
        Dictionary with quotes and historical data for comparison
    """
    try:
        # Convert time range to yfinance parameters
        period, interval = stock_service.get_period_params(time_range)

        # Get comparison data
        comparison = stock_service.compare_stocks(symbols, period, interval)

        if not comparison.get("quotes"):
            return {
                "success": False,
                "error": "No data found",
                "message": f"Could not find data for any of the symbols: {', '.join(symbols)}",
            }

        return {
            "success": True,
            "symbols": list(comparison["quotes"].keys()),
            "time_range": time_range,
            "quotes": comparison["quotes"],
            "historical": comparison["historical"],
            "message": f"Successfully compared {len(comparison['quotes'])} stocks",
        }
    except Exception as e:
        return {"success": False, "error": str(e), "message": f"Failed to compare stocks: {str(e)}"}


@tool
def analyze_stock(symbol: str, time_range: str = "1M") -> dict:
    """
    Analyze a single stock with detailed quote and historical data.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')
        time_range: Time period (1D, 5D, 1M, 6M, YTD, 1Y, 5Y, MAX)

    Returns:
        Dictionary with detailed stock analysis data
    """
    try:
        # Get quote
        quote = stock_service.get_stock_quote(symbol)

        if not quote:
            return {"success": False, "error": "Stock not found", "message": f"Could not find data for {symbol}"}

        # Get historical data
        period, interval = stock_service.get_period_params(time_range)
        historical = stock_service.get_historical_data(symbol, period, interval)

        result = {
            "success": True,
            "symbol": quote.symbol,
            "name": quote.name,
            "time_range": time_range,
            "quote": {
                "price": quote.price,
                "change": quote.change,
                "change_percent": quote.change_percent,
                "prev_close": quote.prev_close,
                "open": quote.open,
                "high": quote.high,
                "low": quote.low,
                "volume": quote.volume,
                "market_cap": quote.market_cap,
                "sector": quote.sector,
                "industry": quote.industry,
            },
        }

        if historical:
            result["historical"] = {
                "dates": historical.dates,
                "prices": historical.prices,
                "normalized": historical.normalized,
                "volumes": historical.volumes,
                "period_performance": historical.normalized[-1] if historical.normalized else 0,
            }

        return result

    except Exception as e:
        return {"success": False, "error": str(e), "message": f"Failed to analyze {symbol}: {str(e)}"}


@tool
def get_related_themes(
    tickers: list[str] | None = None,
    client_id: str | None = None,
    limit: int = 5,
    workgroup: str = "financial-advisor-wg",
    database: str = "financial-advisor-db",
    region: str = "us-west-2",
    profile_name: str = "wealth_management",
) -> dict:
    """
    Get related market themes for stocks or portfolio.
    Calls the market_events_coordinator agent to retrieve themes.

    Args:
        tickers: Optional list of stock tickers to filter themes
        client_id: Optional client ID to get portfolio-specific themes
        limit: Maximum number of themes to return
        workgroup: Redshift workgroup name
        database: Redshift database name
        region: AWS region
        profile_name: AWS profile name

    Returns:
        Dictionary with related market themes
    """
    try:
        # Import here to avoid circular dependency
        from wealth_management_portal_market_events_coordinator.market_events_coordinator_agent.agent import (
            get_market_themes as get_general_themes,
        )
        from wealth_management_portal_market_events_coordinator.market_events_coordinator_agent.agent import (
            get_portfolio_themes,
        )

        # If client_id provided, get portfolio themes
        if client_id:
            result = get_portfolio_themes(
                client_id=client_id,
                limit=limit,
                workgroup=workgroup,
                database=database,
                region=region,
                profile_name=profile_name,
            )
        else:
            # Get general market themes
            result = get_general_themes(
                limit=limit, workgroup=workgroup, database=database, region=region, profile_name=profile_name
            )

        if not result.get("success"):
            return result

        # Filter by tickers if provided
        themes = result.get("themes", [])
        if tickers:
            # Filter themes that mention any of the tickers
            filtered_themes = []
            for theme in themes:
                # Check if any ticker is mentioned in title or summary
                theme_text = f"{theme.get('title', '')} {theme.get('summary', '')}".upper()
                if any(ticker.upper() in theme_text for ticker in tickers):
                    filtered_themes.append(theme)

            themes = filtered_themes[:limit]

        return {
            "success": True,
            "themes_count": len(themes),
            "themes": themes,
            "client_id": client_id,
            "tickers": tickers,
            "message": f"Retrieved {len(themes)} related themes",
        }

    except Exception as e:
        return {"success": False, "error": str(e), "message": f"Failed to get related themes: {str(e)}"}


@tool
def generate_ai_response(query: str, stock_data: dict, themes: list[dict] | None = None) -> dict:
    """
    Generate AI-powered response for stock query with context.

    Args:
        query: Original user query
        stock_data: Stock quotes and historical data
        themes: Optional related market themes for context

    Returns:
        Dictionary with AI-generated response
    """
    try:
        config = Config(region_name="us-east-1", retries={"max_attempts": 3, "mode": "adaptive"})
        bedrock = boto3.client("bedrock-runtime", config=config)
        model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

        # Prepare stock data summary
        quotes = stock_data.get("quotes", {})
        historical = stock_data.get("historical", {})

        stocks_summary = ""
        for symbol, quote in quotes.items():
            hist = historical.get(symbol, {})
            performance = hist.get("normalized", [])[-1] if hist.get("normalized") else 0

            stocks_summary += f"\n{symbol} ({quote.get('name', symbol)}):\n"
            stocks_summary += f"  Current: ${quote.get('price', 0)}\n"
            stocks_summary += f"  Change: {quote.get('change', 0):+.2f} ({quote.get('change_percent', 0):+.2f}%)\n"
            stocks_summary += f"  Period Performance: {performance:+.2f}%\n"
            stocks_summary += f"  Sector: {quote.get('sector', 'Unknown')}\n"

        # Prepare themes context
        themes_context = ""
        if themes:
            themes_context = "\n\nRelated Market Themes:\n"
            for theme in themes[:3]:
                themes_context += f"- {theme.get('title', '')}\n"
                themes_context += f"  Sentiment: {theme.get('sentiment', 'neutral')}\n"
                if theme.get("summary"):
                    themes_context += f"  {theme.get('summary')}\n"

        prompt = f"""Analyze and respond to this stock market query.

User Query: "{query}"

Stock Data:{stocks_summary}{themes_context}

Task: Provide a comprehensive, professional analysis.

Requirements:
1. Answer the user's question directly
2. Reference specific numbers and percentages from the data
3. Highlight key insights and trends
4. Reference relevant market themes if applicable
5. Provide actionable insights
6. Be concise (2-3 paragraphs)
7. Use professional financial analysis tone

Return ONLY the analysis text (no JSON, no markdown formatting)."""

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "temperature": 0.5,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = bedrock.invoke_model(modelId=model_id, body=boto3.compat.json.dumps(request_body))

        response_body = boto3.compat.json.loads(response["body"].read())
        ai_response = response_body["content"][0]["text"].strip()

        return {"success": True, "response": ai_response, "message": "AI response generated successfully"}

    except Exception as e:
        return {"success": False, "error": str(e), "message": f"Failed to generate AI response: {str(e)}"}


@contextmanager
def get_agent(session_id: str):
    yield Agent(
        system_prompt="""
You are a Market Intelligence Chat agent specializing in stock analysis and market insights.

Your capabilities:
1. Parse natural language queries about stocks
2. Fetch real-time stock quotes and historical data
3. Compare multiple stocks with performance analysis
4. Analyze individual stocks with detailed metrics
5. Retrieve related market themes and news context
6. Generate AI-powered insights and recommendations

Use your tools to:
- parse_stock_query: Parse user's natural language query to understand intent and extract tickers
- get_stock_quote: Get real-time quote for a single stock
- compare_stocks: Compare multiple stocks with historical performance
- analyze_stock: Analyze a single stock with detailed data
- get_related_themes: Get related market themes (calls market_events_coordinator agent)
- generate_ai_response: Generate AI-powered analysis with stock data and themes context
- current_time: Get the current date and time

Workflow for stock queries:
1. Parse the query to understand intent and extract tickers
2. Fetch stock data (quotes and historical) based on intent
3. Get related market themes for additional context
4. Generate comprehensive AI response with all context

For portfolio queries:
- Use client_id to get portfolio-specific themes
- Analyze portfolio holdings with market context

For comparison queries:
- Compare multiple stocks side-by-side
- Highlight best/worst performers
- Reference market themes for context

For analysis queries:
- Provide detailed single-stock analysis
- Include sector/industry context
- Reference relevant market themes

Always provide:
- Specific numbers and percentages
- Professional financial analysis tone
- Actionable insights
- Context from market themes when relevant
- Clear, concise responses (2-3 paragraphs)

You are knowledgeable, supportive, and focused on helping users make informed investment decisions.
""",
        tools=[
            parse_stock_query,
            get_stock_quote,
            compare_stocks,
            analyze_stock,
            get_related_themes,
            generate_ai_response,
            current_time,
        ],
    )
