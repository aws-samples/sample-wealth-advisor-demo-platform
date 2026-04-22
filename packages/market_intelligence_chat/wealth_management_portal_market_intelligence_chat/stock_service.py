"""
Stock Data Service - Fetch real-time and historical stock data
Uses Yahoo Finance API (yfinance) for stock data with caching
"""

import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import yfinance as yf


@dataclass
class StockQuote:
    """Real-time stock quote data"""

    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    prev_close: float
    open: float
    high: float
    low: float
    volume: int
    market_cap: float
    sector: str
    industry: str
    updated_at: str


@dataclass
class HistoricalData:
    """Historical stock price data"""

    symbol: str
    dates: list[str]
    prices: list[float]
    normalized: list[float]  # % change from start
    volumes: list[int]
    period: str
    interval: str


class StockDataService:
    """Service for fetching and processing stock data"""

    def __init__(self, cache_dir: str = "/tmp/stock_cache"):
        """
        Initialize stock data service

        Args:
            cache_dir: Directory for caching stock data
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache durations (in seconds)
        self.quote_cache_duration = 300  # 5 minutes
        self.historical_cache_duration = 3600  # 1 hour

        # Rate limiting
        self.min_request_delay = 0.5  # Minimum 0.5 seconds between requests
        self.last_request_time = 0
        self.max_retries = 3
        self.retry_delay = 2  # Base delay for retries

    def _get_cache_path(self, cache_type: str, key: str) -> Path:
        """Get cache file path"""
        cache_hash = hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()
        return self.cache_dir / cache_type / f"{cache_hash}.json"

    def _read_cache(self, cache_type: str, key: str, max_age: int) -> dict | None:
        """Read from cache if not expired"""
        cache_path = self._get_cache_path(cache_type, key)

        if not cache_path.exists():
            return None

        # Check age
        age = datetime.now().timestamp() - cache_path.stat().st_mtime
        if age > max_age:
            return None

        try:
            with open(cache_path) as f:
                return json.load(f)
        except Exception:
            return None

    def _write_cache(self, cache_type: str, key: str, data: dict):
        """Write to cache"""
        cache_path = self._get_cache_path(cache_type, key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        with open(cache_path, "w") as f:
            json.dump(data, f)

    def _rate_limit(self):
        """Implement rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_request_delay:
            sleep_time = self.min_request_delay - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _retry_with_backoff(self, func, *args, **kwargs):
        """Retry a function with exponential backoff"""
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = str(e)

                # Check if it's a rate limit error
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    if attempt < self.max_retries - 1:
                        # Exponential backoff with jitter
                        delay = self.retry_delay * (2**attempt) + random.uniform(0, 1)
                        print(f"Rate limited. Retrying in {delay:.1f}s... (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"Rate limit exceeded after {self.max_retries} attempts")
                        raise
                else:
                    # For other errors, don't retry
                    raise

        return None

    def get_stock_quote(self, symbol: str) -> StockQuote | None:
        """
        Get real-time stock quote

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            StockQuote object or None if error
        """
        # Check cache
        cache_key = f"quote_{symbol.upper()}"
        cached = self._read_cache("quotes", cache_key, self.quote_cache_duration)

        if cached:
            return StockQuote(**cached)

        try:

            def fetch_quote():
                ticker = yf.Ticker(symbol)
                return ticker.info

            info = self._retry_with_backoff(fetch_quote)

            if not info:
                return None

            # Get current price
            current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
            prev_close = info.get("previousClose", 0)

            # Calculate change
            change = current_price - prev_close
            change_percent = (change / prev_close * 100) if prev_close else 0

            quote = StockQuote(
                symbol=symbol.upper(),
                name=info.get("longName", symbol),
                price=round(current_price, 2),
                change=round(change, 2),
                change_percent=round(change_percent, 2),
                prev_close=round(prev_close, 2),
                open=round(info.get("open", 0), 2),
                high=round(info.get("dayHigh", 0), 2),
                low=round(info.get("dayLow", 0), 2),
                volume=info.get("volume", 0),
                market_cap=info.get("marketCap", 0),
                sector=info.get("sector", "Unknown"),
                industry=info.get("industry", "Unknown"),
                updated_at=datetime.now().isoformat(),
            )

            # Cache the result
            self._write_cache("quotes", cache_key, asdict(quote))

            return quote

        except Exception as e:
            print(f"Error fetching quote for {symbol}: {e}")
            return None

    def get_historical_data(self, symbol: str, period: str = "1mo", interval: str = "1d") -> HistoricalData | None:
        """
        Get historical stock data

        Args:
            symbol: Stock ticker symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)

        Returns:
            HistoricalData object or None if error
        """
        # Check cache
        cache_key = f"historical_{symbol.upper()}_{period}_{interval}"
        cached = self._read_cache("historical", cache_key, self.historical_cache_duration)

        if cached:
            return HistoricalData(**cached)

        try:

            def fetch_historical():
                ticker = yf.Ticker(symbol)
                return ticker.history(period=period, interval=interval)

            hist = self._retry_with_backoff(fetch_historical)

            if hist is None or hist.empty:
                return None

            # Extract data
            dates = [d.strftime("%Y-%m-%d %H:%M:%S") for d in hist.index]
            prices = hist["Close"].tolist()
            volumes = hist["Volume"].tolist()

            # Calculate normalized performance (% change from start)
            start_price = prices[0]
            normalized = [((p - start_price) / start_price * 100) for p in prices]

            historical = HistoricalData(
                symbol=symbol.upper(),
                dates=dates,
                prices=[round(p, 2) for p in prices],
                normalized=[round(n, 2) for n in normalized],
                volumes=[int(v) for v in volumes],
                period=period,
                interval=interval,
            )

            # Cache the result
            self._write_cache("historical", cache_key, asdict(historical))

            return historical

        except Exception as e:
            print(f"Error fetching historical data for {symbol}: {e}")
            return None

    def get_multiple_quotes(self, symbols: list[str]) -> dict[str, StockQuote]:
        """
        Get quotes for multiple stocks

        Args:
            symbols: List of stock ticker symbols

        Returns:
            Dictionary mapping symbol to StockQuote
        """
        quotes = {}

        for symbol in symbols:
            quote = self.get_stock_quote(symbol)
            if quote:
                quotes[symbol.upper()] = quote

        return quotes

    def compare_stocks(self, symbols: list[str], period: str = "1mo", interval: str = "1d") -> dict:
        """
        Compare multiple stocks

        Args:
            symbols: List of stock ticker symbols
            period: Time period
            interval: Data interval

        Returns:
            Dictionary with quotes and historical data
        """
        # Get quotes
        quotes = self.get_multiple_quotes(symbols)

        # Get historical data
        historical = {}
        for symbol in symbols:
            hist = self.get_historical_data(symbol, period, interval)
            if hist:
                historical[symbol.upper()] = hist

        return {
            "quotes": {k: asdict(v) for k, v in quotes.items()},
            "historical": {k: asdict(v) for k, v in historical.items()},
        }

    def get_period_params(self, period_str: str) -> tuple[str, str]:
        """
        Convert period string to yfinance parameters

        Args:
            period_str: Period string (1D, 5D, 1M, 6M, YTD, 1Y, 5Y, MAX)

        Returns:
            Tuple of (period, interval)
        """
        period_map = {
            "1D": ("1d", "5m"),
            "5D": ("5d", "30m"),
            "1M": ("1mo", "1d"),
            "6M": ("6mo", "1d"),
            "YTD": ("ytd", "1d"),
            "1Y": ("1y", "1d"),
            "5Y": ("5y", "1wk"),
            "MAX": ("max", "1mo"),
        }

        return period_map.get(period_str.upper(), ("1mo", "1d"))
