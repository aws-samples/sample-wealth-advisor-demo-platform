# Extended repository for date-range performance queries
from collections.abc import Callable
from datetime import date

from wealth_management_portal_portfolio_data_access.models.performance import PerformanceRecord
from wealth_management_portal_portfolio_data_access.repositories.base import BaseRepository


class PerformanceRepository(BaseRepository[PerformanceRecord]):
    """Performance repository with date-range filtering."""

    def __init__(self, conn_factory: Callable):
        super().__init__(
            conn_factory,
            PerformanceRecord,
            "public.performance",
            {
                "performance_id",
                "portfolio_id",
                "period",
                "period_start_date",
                "period_end_date",
                "time_weighted_return",
                "benchmark_return",
                "beginning_value",
                "ending_value",
            },
        )
        self._conn_factory = conn_factory

    def get_for_period(self, portfolio_id: str, start: date, end: date) -> list[PerformanceRecord]:
        """Get performance records within a date range, ordered by start date."""
        sql = """
            SELECT * FROM public.performance
            WHERE portfolio_id = %s
              AND period_start_date >= %s
              AND period_end_date <= %s
            ORDER BY period_start_date
        """
        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql, [portfolio_id, start, end])
            cols = [d[0] for d in cur.description]
            return [self._model.model_validate(dict(zip(cols, row, strict=True))) for row in cur.fetchall()]
