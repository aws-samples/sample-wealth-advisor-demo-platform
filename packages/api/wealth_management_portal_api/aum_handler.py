"""Handler for AUM trends endpoint."""

from pydantic import BaseModel
from wealth_management_portal_portfolio_data_access.repositories.aum_repository import (
    AUMRepository,
)

from .init import logger


class AUMTrendsResponse(BaseModel):
    """Response model for AUM trends."""

    trends: list[dict]


class DashboardSummaryResponse(BaseModel):
    """Response model for dashboard summary."""

    total_aum: float
    total_aum_change: float
    total_aum_change_percent: float
    active_clients: int
    active_clients_change: int
    total_fees: float
    fees_change: float
    avg_portfolio_return_pct: float
    avg_portfolio_return_value: float


def get_aum_trends(advisor_id: str | None = None, limit: int = 12) -> AUMTrendsResponse:
    """Get AUM trends from Redshift."""
    try:
        logger.info("Fetching AUM trends", extra={"advisor_id": advisor_id, "limit": limit})
        repo = AUMRepository()

        trends = repo.get_total_aum_trends(limit)
        logger.info("Got %d total AUM records", len(trends))

        # Convert to string format
        trends = [
            {
                "report_month": str(item["report_month"]),
                "total_aum": float(item["total_aum"]),
            }
            for item in trends
        ]

        # Reverse to show oldest to newest
        trends.reverse()

        logger.info("Returning %d trends", len(trends))
        return AUMTrendsResponse(trends=trends)

    except Exception:
        logger.exception("Error fetching AUM trends")
        return AUMTrendsResponse(trends=[])


def get_dashboard_summary() -> DashboardSummaryResponse:
    """Get dashboard summary metrics from Redshift."""
    try:
        logger.info("Fetching dashboard summary")
        repo = AUMRepository()

        summary = repo.get_dashboard_summary()
        logger.info("Got dashboard summary")

        # Calculate percentage change
        total_aum_latest = float(summary.get("total_aum_latest_month", 0))
        total_aum_previous = float(summary.get("total_aum_previous_month", 0))
        aum_change = float(summary.get("aum_change", 0))
        aum_change_percent = (aum_change / total_aum_previous * 100) if total_aum_previous > 0 else 0

        active_clients_latest = int(summary.get("active_clients_latest_month", 0))
        active_clients_previous = int(summary.get("active_clients_previous_month", 0))
        active_clients_change = active_clients_latest - active_clients_previous

        total_fees_latest = float(summary.get("total_fees_latest_month", 0))
        fees_change = float(summary.get("fees_change", 0))

        return DashboardSummaryResponse(
            total_aum=total_aum_latest,
            total_aum_change=aum_change,
            total_aum_change_percent=aum_change_percent,
            active_clients=active_clients_latest,
            active_clients_change=active_clients_change,
            total_fees=total_fees_latest,
            fees_change=fees_change,
            avg_portfolio_return_pct=float(summary.get("avg_portfolio_return_pct", 0)),
            avg_portfolio_return_value=float(summary.get("avg_portfolio_return_value", 0)),
        )

    except Exception:
        logger.exception("Error fetching dashboard summary")
        # Return default data on error
        return DashboardSummaryResponse(
            total_aum=0,
            total_aum_change=0,
            total_aum_change_percent=0,
            active_clients=0,
            active_clients_change=0,
            total_fees=0,
            fees_change=0,
            avg_portfolio_return_pct=0,
            avg_portfolio_return_value=0,
        )


class AUMDataPoint(BaseModel):
    month: str
    value: float


class ClientAUMResponse(BaseModel):
    success: bool
    data_points: int
    aum_data: list[AUMDataPoint]
    message: str


def get_client_aum(client_id: str, months: int = 12) -> ClientAUMResponse:
    """Get AUM data for a client from investor_monthly_aum view"""
    try:
        repo = AUMRepository()
        rows = repo.get_client_aum(client_id, months)

        # Reverse to get chronological order
        rows.reverse()

        aum_data = [AUMDataPoint(month=row["month"], value=float(row.get("aum_value", 0))) for row in rows]

        return ClientAUMResponse(
            success=True,
            data_points=len(aum_data),
            aum_data=aum_data,
            message=f"Retrieved {len(aum_data)} months of AUM data",
        )

    except Exception as e:
        return ClientAUMResponse(
            success=False,
            data_points=0,
            aum_data=[],
            message=f"Error retrieving AUM data: {str(e)}",
        )
