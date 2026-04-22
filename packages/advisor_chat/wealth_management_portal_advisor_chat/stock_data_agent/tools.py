"""Stock data agent tools — live stock quotes via Yahoo Finance."""

import json

import yfinance as yf
from strands import tool


def _build_insights(raw: dict) -> str:
    """Generate data-driven insights from stock data — no LLM needed."""
    points = []
    for sym, d in raw.items():
        price, high52, low52 = d["price"], d["high52"], d["low52"]
        if not price or not high52:
            continue
        range52 = high52 - low52 if high52 and low52 else 0
        pos = ((price - low52) / range52 * 100) if range52 else 0
        if pos > 90:
            points.append(f"**{sym}** is trading near its 52-week high (top {100 - pos:.0f}% of range)")
        elif pos < 10:
            points.append(f"**{sym}** is trading near its 52-week low (bottom {pos:.0f}% of range)")
        if d.get("pe") and isinstance(d["pe"], (int, float)):
            pe = d["pe"]
            if pe > 40:
                points.append(f"**{sym}** P/E of {pe:.1f} indicates a high-growth premium valuation")
            elif pe < 15:
                points.append(f"**{sym}** P/E of {pe:.1f} suggests a value opportunity")
        if abs(d["change_pct"]) > 3:
            direction = "up" if d["change_pct"] > 0 else "down"
            points.append(f"**{sym}** is {direction} {abs(d['change_pct']):.1f}% today — significant move")
    symbols = list(raw.keys())
    if len(symbols) >= 2:
        best = max(symbols, key=lambda s: raw[s]["change_pct"])
        worst = min(symbols, key=lambda s: raw[s]["change_pct"])
        if raw[best]["change_pct"] != raw[worst]["change_pct"]:
            points.append(
                f"**{best}** is outperforming today ({raw[best]['change_pct']:+.2f}%) "
                f"vs **{worst}** ({raw[worst]['change_pct']:+.2f}%)"
            )
    if not points:
        return ""
    return "### 💡 Key Insights\n\n" + "\n".join(f"- {p}" for p in points)


@tool
def get_stock_quotes(tickers: list[str]) -> str:
    """Get live stock quotes directly. FASTEST option for stock prices.

    Use for: stock prices, quotes, market data for specific tickers.
    Maps company names to tickers: Apple→AAPL, Microsoft→MSFT, Google→GOOGL,
    Amazon→AMZN, Tesla→TSLA, Nvidia→NVDA, Meta→META.

    Args:
        tickers: Stock symbols (e.g. ['AAPL', 'MSFT']).

    Returns:
        Markdown table with stock data and embedded structured quotes.
    """
    quotes_json = []
    table_data = {}
    raw = {}
    for symbol in tickers[:10]:
        try:
            info = yf.Ticker(symbol).info or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
            prev = info.get("previousClose") or info.get("regularMarketPreviousClose", 0)
            change = round(price - prev, 2) if price and prev else 0
            change_pct = round((change / prev) * 100, 2) if prev else 0
            raw[symbol] = {
                "price": price,
                "prev": prev,
                "change": change,
                "change_pct": change_pct,
                "high52": info.get("fiftyTwoWeekHigh", 0),
                "low52": info.get("fiftyTwoWeekLow", 0),
                "pe": info.get("trailingPE"),
                "mcap": info.get("marketCap", 0),
                "name": info.get("shortName", symbol),
            }
            table_data[symbol] = {
                "Name": info.get("shortName", symbol),
                "Price": f"${price:,.2f}" if price else "N/A",
                "Change": f"${change:+,.2f} ({change_pct:+.2f}%)",
                "Prev Close": f"${prev:,.2f}" if prev else "N/A",
                "Day Range": f"${info.get('dayLow', 0):,.2f} - ${info.get('dayHigh', 0):,.2f}",
                "52W Range": f"${info.get('fiftyTwoWeekLow', 0):,.2f} - ${info.get('fiftyTwoWeekHigh', 0):,.2f}",
                "Volume": f"{(info.get('volume') or 0):,}",
                "Market Cap": f"${info.get('marketCap', 0):,.0f}" if info.get("marketCap") else "N/A",
                "P/E Ratio": f"{info.get('trailingPE', 'N/A')}",
                "Sector": info.get("sector", "N/A"),
            }
            quotes_json.append(
                {
                    "symbol": symbol,
                    "name": info.get("shortName", symbol),
                    "price": price or 0,
                    "change": change,
                    "changePercent": change_pct,
                    "prevClose": prev or 0,
                }
            )
        except Exception:
            table_data[symbol] = {"error": f"Could not fetch data for {symbol}"}

    if not table_data:
        return "No data found."

    symbols = list(table_data.keys())
    header = "| Metric | " + " | ".join(symbols) + " |"
    sep = "| --- | " + " | ".join(["---"] * len(symbols)) + " |"
    rows = [header, sep]
    for key in list(table_data[symbols[0]].keys()):
        vals = " | ".join(str(table_data[s].get(key, "N/A")) for s in symbols)
        rows.append(f"| {key} | {vals} |")
    table = "\n".join(rows)
    insights = _build_insights(raw)
    return f"{table}\n\n{insights}\n\n<!--QUOTES:{json.dumps(quotes_json)}-->"
