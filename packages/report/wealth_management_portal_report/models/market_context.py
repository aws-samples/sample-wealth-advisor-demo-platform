# Market context data contract
from datetime import date

from pydantic import BaseModel


class BenchmarkReturn(BaseModel):
    """Return figures for a market benchmark over standard periods."""

    name: str  # e.g., "S&P 500"
    ytd: float
    one_year: float


class SectorPerformance(BaseModel):
    """Year-to-date performance for a market sector."""

    sector: str
    ytd: float


class MarketEvent(BaseModel):
    """Notable market event relevant to the client's portfolio."""

    date: date
    description: str
    impact: str  # e.g., "Negative", "Positive", "Neutral"


class MarketContext(BaseModel):
    """Market environment snapshot for contextualizing portfolio performance."""

    as_of_date: date
    benchmark_returns: list[BenchmarkReturn]
    sector_performance: list[SectorPerformance]
    notable_events: list[MarketEvent]
