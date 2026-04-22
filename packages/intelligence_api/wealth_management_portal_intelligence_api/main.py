import json
import logging
import os
import re
from pathlib import Path

import boto3
import botocore.config
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables from root .env file (local dev only)
try:
    root_dir = Path(__file__).parent.parent.parent.parent
    env_path = root_dir / ".env"
    load_dotenv(dotenv_path=env_path)
except IndexError:
    load_dotenv()

from .client_search_handler import ClientSearchRequest, ClientSearchResponse, search_clients_nl  # noqa: E402

# Lazy import for market_intelligence_chat (not bundled in Lambda)
analyze_stock = None
get_agent = None
parse_stock_query = None


def _ensure_chat_imports():
    global analyze_stock, get_agent, parse_stock_query
    if analyze_stock is None:
        from wealth_management_portal_market_intelligence_chat.chat_agent.agent import (
            analyze_stock as _analyze_stock,
        )
        from wealth_management_portal_market_intelligence_chat.chat_agent.agent import (
            get_agent as _get_agent,
        )
        from wealth_management_portal_market_intelligence_chat.chat_agent.agent import (
            parse_stock_query as _parse_stock_query,
        )

        analyze_stock = _analyze_stock
        get_agent = _get_agent
        parse_stock_query = _parse_stock_query


from datetime import UTC  # noqa: E402

from .init import app, lambda_handler, tracer  # noqa: E402

handler = lambda_handler
logger = logging.getLogger(__name__)

# AgentCore routing agent ARN (set by CDK)
ROUTING_AGENT_ARN = os.environ.get("ROUTING_AGENT_ARN")


def _call_routing_agent(message: str) -> str:
    """Invoke the routing agent via AgentCore and return the response text."""
    if not ROUTING_AGENT_ARN:
        return "Routing agent not configured."
    client = boto3.client(
        "bedrock-agentcore",
        region_name=os.environ.get("AWS_REGION", "us-west-2"),
        config=botocore.config.Config(read_timeout=300),
    )
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {
                "message": {
                    "kind": "message",
                    "role": "user",
                    "messageId": f"lambda-{os.urandom(8).hex()}",
                    "parts": [{"kind": "text", "text": message}],
                }
            },
        }
    )
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=ROUTING_AGENT_ARN,
        runtimeSessionId=f"chat-{os.urandom(16).hex()}",
        payload=payload,
    )
    body = json.loads(resp["response"].read())
    result = body.get("result", {})
    # Extract text from artifacts
    for artifact in result.get("artifacts", []):
        for part in artifact.get("parts", []):
            if part.get("kind") == "text" and part.get("text"):
                return part["text"]
    return str(body)


class ChatRequest(BaseModel):
    message: str
    session_id: str


class StockData(BaseModel):
    symbol: str
    price: float
    change: float
    changePercent: float
    chartData: list
    keyDrivers: list[str]
    sources: list[dict]


class ChatResponse(BaseModel):
    message: str
    stockData: StockData | None = None


@app.post("/chat")
@tracer.capture_method
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat endpoint using market intelligence agent."""
    return await handle_chat(request.message, request.session_id)


@app.post("/advisor-chat")
@tracer.capture_method
async def advisor_chat(request: ChatRequest) -> ChatResponse:
    """Chat endpoint using A2A routing agent via AgentCore."""
    try:
        text = _call_routing_agent(request.message)
        text = re.sub(r"<thinking>[\s\S]*?</thinking>\s*", "", text).strip()
        return ChatResponse(message=text)
    except Exception as e:
        logger.exception("Advisor chat error")
        return ChatResponse(message=f"Sorry, I encountered an error: {e}")


@app.post("/client-search")
@tracer.capture_method
async def client_search(request: ClientSearchRequest) -> ClientSearchResponse:
    """Natural language client search endpoint."""
    return search_clients_nl(request.query)


# --- Chart endpoint (lightweight, no yfinance dependency) ---

_CHART_COLORS = ["#4285f4", "#ea8600", "#1a73e8", "#c5621c", "#34a853", "#ea4335"]
_RANGE_MAP = {
    "1D": ("1d", "5m"),
    "5D": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "6M": ("6mo", "1d"),
    "YTD": ("ytd", "1d"),
    "1Y": ("1y", "1wk"),
    "5Y": ("5y", "1mo"),
    "MAX": ("max", "1mo"),
}


def _fetch_yahoo(symbol: str, yf_range: str, interval: str) -> dict | None:
    """Fetch chart data from Yahoo Finance v8 API using stdlib only."""
    import urllib.request

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={yf_range}&interval={interval}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        logger.warning("Yahoo fetch error for %s: %s", symbol, e)
        return None


@app.get("/chart")
@tracer.capture_method
async def chart(tickers: str, range: str = "1M"):
    """Lightweight chart data — calls Yahoo Finance directly, no agent."""
    yf_range, interval = _RANGE_MAP.get(range, ("1mo", "1d"))
    quotes, chart_series, all_dates = [], [], []
    if interval == "5m":
        fmt = "%H:%M"
    elif interval == "30m":
        fmt = "%b %d %H:%M"
    elif interval in ("1wk", "1mo"):
        fmt = "%b %d, %Y"
    else:
        fmt = "%b %d"

    for i, symbol in enumerate(tickers.split(",")[:6]):
        symbol = symbol.strip().upper()
        if not symbol:
            continue
        color = _CHART_COLORS[i % len(_CHART_COLORS)]
        data = _fetch_yahoo(symbol, yf_range, interval)
        if not data:
            continue
        result = (data.get("chart", {}).get("result") or [None])[0]
        if not result:
            continue

        meta = result.get("meta", {})
        price = meta.get("regularMarketPrice", 0)
        prev = meta.get("chartPreviousClose") or meta.get("previousClose", 0)
        change = round(price - prev, 2) if price and prev else 0
        change_pct = round((change / prev) * 100, 2) if prev else 0

        quotes.append(
            {
                "symbol": symbol,
                "name": meta.get("shortName", symbol),
                "price": price,
                "change": change,
                "changePercent": change_pct,
                "prevClose": prev,
                "color": color,
            }
        )

        timestamps = result.get("timestamp") or []
        closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
        if timestamps and closes:
            from datetime import datetime

            dates = [datetime.fromtimestamp(t, tz=UTC).strftime(fmt) for t in timestamps]
            base = closes[0] or 1
            normalized = [round(((c or base) / base - 1) * 100, 2) for c in closes]
            chart_series.append({"symbol": symbol, "values": normalized, "color": color})
            if len(dates) > len(all_dates):
                all_dates = dates

    return {"quotes": quotes, "chartData": {"dates": all_dates, "series": chart_series}, "timeRange": range}


async def handle_chat(message: str, session_id: str) -> ChatResponse:
    """Handle chat using market intelligence agent."""
    _ensure_chat_imports()
    try:
        # Parse query to check if it's stock-related
        parsed = parse_stock_query(message)
        tickers = parsed.get("tickers", [])

        # Use the Strands Agent for the response
        with get_agent(session_id) as agent:
            result = agent(message)

        # Extract clean text from AgentResult
        response_text = str(result) if result else "I couldn't process that request."

        # Clean up the response - remove tool output formatting
        if "Tool Outputs:" in response_text:
            parts = response_text.split("Tool Outputs:")
            if len(parts) > 1:
                response_text = parts[-1].strip()

        # Format the response with stock data if applicable
        if tickers and len(tickers) == 1:
            ticker = tickers[0]
            time_range = parsed.get("time_range", "1M")
            analysis = analyze_stock(ticker, time_range)

            if analysis.get("success"):
                quote = analysis.get("quote", {})
                hist = analysis.get("historical", {})

                price = quote.get("price", 0)
                change = quote.get("change", 0)
                change_pct = quote.get("change_percent", 0)
                direction = "up" if change >= 0 else "down"

                formatted_response = f"""**{analysis.get("name", ticker)} ({ticker})**

**Current Price:** ${price:.2f}
**Change:** ${abs(change):.2f} ({abs(change_pct):.2f}%) {direction}

**Market Data:**
• Open: ${quote.get("open", 0):.2f}
• High: ${quote.get("high", 0):.2f}
• Low: ${quote.get("low", 0):.2f}
• Previous Close: ${quote.get("prev_close", 0):.2f}
• Volume: {quote.get("volume", 0):,}

**Analysis:**
{response_text}"""

                chart_data = []
                if hist.get("dates") and hist.get("prices"):
                    for date, price in zip(hist["dates"][:20], hist["prices"][:20], strict=False):
                        chart_data.append({"time": date.split()[0] if " " in date else date, "price": price})

                sources = [
                    {
                        "title": f"{ticker} Real-time Stock Quote",
                        "url": f"https://finance.yahoo.com/quote/{ticker}",
                        "source": "Yahoo Finance",
                    },
                    {
                        "title": f"{ticker} Company Profile & News",
                        "url": f"https://www.google.com/finance/quote/{ticker}:NASDAQ",
                        "source": "Google Finance",
                    },
                    {
                        "title": f"{ticker} Market Data & Analysis",
                        "url": f"https://www.marketwatch.com/investing/stock/{ticker.lower()}",
                        "source": "MarketWatch",
                    },
                ]

                stock_data = StockData(
                    symbol=analysis.get("name", ticker),
                    price=quote.get("price", 0),
                    change=quote.get("change", 0),
                    changePercent=quote.get("change_percent", 0),
                    chartData=chart_data,
                    keyDrivers=[],
                    sources=sources,
                )

                return ChatResponse(message=formatted_response, stockData=stock_data)

        return ChatResponse(message=response_text)

    except Exception as e:
        import traceback

        traceback.print_exc()
        return ChatResponse(message=f"Sorry, I encountered an error: {str(e)}")
