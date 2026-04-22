# Redshift-mirroring model for portfolio performance
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class PerformanceRecord(BaseModel):
    """Performance record from Redshift performance table."""

    performance_id: str
    portfolio_id: str
    period: str
    period_start_date: date
    period_end_date: date
    time_weighted_return: Decimal | None = None
    benchmark_return: Decimal | None = None
    beginning_value: Decimal | None = None
    ending_value: Decimal | None = None
