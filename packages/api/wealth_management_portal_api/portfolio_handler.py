"""Handler for aggregate portfolio endpoints."""

from pydantic import BaseModel
from wealth_management_portal_portfolio_data_access.repositories.data_api_base_repository import (
    DataApiBaseRepository,
)

from .init import logger


class Holding(BaseModel):
    ticker: str | None = None
    security_name: str | None = None
    sector: str | None = None
    asset_class: str | None = None
    total_shares: float = 0
    avg_price: float = 0
    total_value: float = 0
    total_gain_loss: float = 0


class Allocation(BaseModel):
    name: str
    value: float
    percentage: float = 0


class PortfolioSummaryResponse(BaseModel):
    total_value: float
    top_holdings: list[Holding]
    sector_allocation: list[Allocation]
    asset_allocation: list[Allocation]


def get_portfolio_summary() -> PortfolioSummaryResponse:
    """Get aggregate portfolio summary across all clients."""
    try:
        repo = DataApiBaseRepository()

        holdings_sql = """
            SELECT s.ticker, s.security_name, s.sector, s.asset_class,
                   SUM(h.quantity) as total_shares,
                   AVG(h.current_price) as avg_price,
                   SUM(h.market_value) as total_value,
                   SUM(h.unrealized_gain_loss) as total_gain_loss
            FROM holdings h
            JOIN securities s
                ON CAST(h.security_id AS varchar) = CAST(s.security_id AS varchar)
            GROUP BY s.ticker, s.security_name, s.sector, s.asset_class
            ORDER BY total_value DESC
            LIMIT 20
        """
        holdings_rows = repo._execute_and_wait(holdings_sql)

        sector_sql = """
            SELECT s.sector AS name, SUM(h.market_value) as value
            FROM holdings h
            JOIN securities s
                ON CAST(h.security_id AS varchar) = CAST(s.security_id AS varchar)
            WHERE s.sector IS NOT NULL AND s.sector != ''
            GROUP BY s.sector
            ORDER BY value DESC
        """
        sector_rows = repo._execute_and_wait(sector_sql)

        asset_sql = """
            SELECT s.asset_class AS name, SUM(h.market_value) as value
            FROM holdings h
            JOIN securities s
                ON CAST(h.security_id AS varchar) = CAST(s.security_id AS varchar)
            WHERE s.asset_class IS NOT NULL AND s.asset_class != ''
            GROUP BY s.asset_class
            ORDER BY value DESC
        """
        asset_rows = repo._execute_and_wait(asset_sql)

        total_value = sum(float(r.get("total_value") or 0) for r in holdings_rows)

        top_holdings = [
            Holding(
                ticker=r.get("ticker"),
                security_name=r.get("security_name"),
                sector=r.get("sector"),
                asset_class=r.get("asset_class"),
                total_shares=float(r.get("total_shares") or 0),
                avg_price=float(r.get("avg_price") or 0),
                total_value=float(r.get("total_value") or 0),
                total_gain_loss=float(r.get("total_gain_loss") or 0),
            )
            for r in holdings_rows
        ]

        sector_total = sum(float(r.get("value") or 0) for r in sector_rows)
        sector_allocation = [
            Allocation(
                name=r.get("name", "Unknown"),
                value=float(r.get("value") or 0),
                percentage=round(float(r.get("value") or 0) / sector_total * 100, 1) if sector_total > 0 else 0,
            )
            for r in sector_rows
        ]

        asset_total = sum(float(r.get("value") or 0) for r in asset_rows)
        asset_allocation = [
            Allocation(
                name=r.get("name", "Unknown"),
                value=float(r.get("value") or 0),
                percentage=round(float(r.get("value") or 0) / asset_total * 100, 1) if asset_total > 0 else 0,
            )
            for r in asset_rows
        ]

        return PortfolioSummaryResponse(
            total_value=total_value,
            top_holdings=top_holdings,
            sector_allocation=sector_allocation,
            asset_allocation=asset_allocation,
        )

    except Exception:
        logger.exception("Error fetching portfolio summary")
        return PortfolioSummaryResponse(total_value=0, top_holdings=[], sector_allocation=[], asset_allocation=[])
