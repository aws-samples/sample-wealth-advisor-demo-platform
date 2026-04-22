"""Build structured marketData using Pattern B (agent JSON → backend → Plotly)."""

import logging
from functools import lru_cache

import yfinance as yf

logger = logging.getLogger(__name__)

COLORS = ["#4285f4", "#ea8600", "#1a73e8", "#c5621c", "#34a853", "#ea4335"]

PERIOD_MAP = {
    "1D": ("1d", "5m"),
    "5D": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "6M": ("6mo", "1d"),
    "YTD": ("ytd", "1d"),
    "1Y": ("1y", "1wk"),
    "5Y": ("5y", "1mo"),
    "MAX": ("max", "1mo"),
}

# -------------------------
# Time Range
# -------------------------


def _get_period_interval(time_range: str):
    if time_range == "YTD":
        return "ytd", "1d"
    elif time_range == "MAX":
        return "max", "1mo"
    return PERIOD_MAP.get(time_range, ("1mo", "1d"))


# -------------------------
# Cached Fetch
# -------------------------


@lru_cache(maxsize=128)
def _get_ticker(symbol: str):
    return yf.Ticker(symbol)


@lru_cache(maxsize=256)
def _fetch_history_cached(symbol: str, period: str, interval: str):
    return yf.Ticker(symbol).history(period=period, interval=interval)


# -------------------------
# Quote
# -------------------------


def _fetch_quote(symbol: str, color: str) -> dict | None:
    try:
        ticker = _get_ticker(symbol)
        info = ticker.info or {}

        price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose", 0)

        change = round(price - prev, 2) if price and prev else 0
        change_pct = round((change / prev) * 100, 2) if prev else 0

        return {
            "symbol": symbol,
            "name": info.get("shortName", symbol),
            "price": price or 0,
            "change": change,
            "changePercent": change_pct,
            "prevClose": prev or 0,
            "color": color,
        }

    except Exception as e:
        logger.warning("Quote error for %s: %s", symbol, e)
        return None


# -------------------------
# History
# -------------------------


def _fetch_history(symbol: str, color: str, period: str, interval: str):
    try:
        hist = _fetch_history_cached(symbol, period, interval)

        if hist.empty:
            return None, [], [], []

        dates = [d.isoformat() for d in hist.index]
        prices = [round(p, 2) for p in hist["Close"]]
        volumes = list(hist["Volume"])

        return (
            {
                "symbol": symbol,
                "values": prices,
                "color": color,
            },
            dates,
            prices,
            volumes,
        )

    except Exception as e:
        logger.warning("History error for %s: %s", symbol, e)
        return None, [], [], []


# -------------------------
# Intelligence
# -------------------------


def _build_chart_meta(prices: list[float]) -> dict:
    if not prices or len(prices) < 2:
        return {}

    change = prices[-1] - prices[0]

    trend = "bullish" if change > 0 else "bearish" if change < 0 else "neutral"

    momentum = ("up" if prices[-1] > prices[-3] else "down") if len(prices) >= 3 else "neutral"

    return {
        "trend": trend,
        "momentum": momentum,
        "change": round(change, 2),
    }


def _compute_levels(prices: list[float]) -> dict:
    if len(prices) < 10:
        return {}

    window = prices[-20:] if len(prices) >= 20 else prices

    return {
        "support": round(min(window), 2),
        "resistance": round(max(window), 2),
    }


def _compute_drawdown(prices: list[float]) -> dict | None:
    if not prices:
        return None

    peak = prices[0]
    max_dd = 0

    for p in prices:
        if p > peak:
            peak = p
        dd = (p - peak) / peak
        if dd < max_dd:
            max_dd = dd

    if max_dd < -0.03:
        return {
            "type": "drawdown",
            "value": round(max_dd * 100, 2),
        }

    return None


def _relative_position(prices: list[float]) -> str:
    low = min(prices)
    high = max(prices)
    current = prices[-1]

    pct = (current - low) / (high - low + 1e-6)

    if pct > 0.8:
        return "near_high"
    elif pct < 0.2:
        return "near_low"
    return "mid_range"


def _volatility(prices: list[float]) -> str:
    if len(prices) < 2:
        return "low"

    change = abs((prices[-1] - prices[0]) / prices[0])

    if change > 0.05:
        return "high"
    elif change > 0.02:
        return "moderate"
    return "low"


# -------------------------
# Main Builder (Pattern B)
# -------------------------


def build_market_data(request: dict) -> dict | None:
    """
    request = {
        "tickers": ["AAPL","MSFT"],
        "intent": "comparison",
        "timeRange": "1M"
    }
    """

    tickers = request.get("tickers", [])
    time_range = request.get("timeRange", "1M")

    if not tickers:
        return None

    period, interval = _get_period_interval(time_range)

    quotes = []
    chart_series = []
    all_dates = []

    per_stock_meta = {}
    annotations = []
    levels = {}

    for i, symbol in enumerate(tickers[:6]):
        symbol = symbol.strip().upper()
        color = COLORS[i % len(COLORS)]

        # Quote
        q = _fetch_quote(symbol, color)
        if q:
            quotes.append(q)

        # History
        series, dates, prices, volumes = _fetch_history(symbol, color, period, interval)

        if series:
            chart_series.append(series)

            if len(dates) > len(all_dates):
                all_dates = dates

            # Per-stock intelligence
            per_stock_meta[symbol] = {
                **_build_chart_meta(prices),
                "position": _relative_position(prices),
                "volatility": _volatility(prices),
            }

            # Primary stock signals
            if i == 0:
                levels = _compute_levels(prices)

                dd = _compute_drawdown(prices)
                if dd:
                    annotations.append(dd)

    return {
        "quotes": quotes,
        "chartData": {
            "dates": all_dates,
            "series": chart_series,
        },
        "perStockMeta": per_stock_meta,
        "levels": levels,
        "annotations": annotations,
        "timeRange": time_range,
        "compareMode": "normalized" if len(chart_series) > 1 else "absolute",
        "benchmark": "SPY" if len(chart_series) == 1 else None,
    }
