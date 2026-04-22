# Extended repository for portfolio queries requiring joins
from collections.abc import Callable

from wealth_management_portal_portfolio_data_access.models.portfolio import PortfolioRecord
from wealth_management_portal_portfolio_data_access.repositories.base import BaseRepository


class PortfolioRepository(BaseRepository[PortfolioRecord]):
    """Portfolio repository with join queries for holdings + securities."""

    def __init__(self, conn_factory: Callable):
        super().__init__(
            conn_factory,
            PortfolioRecord,
            "public.portfolios",
            {
                "portfolio_id",
                "account_id",
                "portfolio_name",
                "investment_model",
                "target_allocation",
                "benchmark",
                "inception_date",
            },
        )
        self._conn_factory = conn_factory

    def get_holdings_with_securities(self, portfolio_id: str) -> list[dict]:
        """Holdings enriched with security details."""
        sql = """
            SELECT *
            FROM public.client_portfolio_holdings
            WHERE portfolio_id = %s
        """
        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql, [portfolio_id])
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
