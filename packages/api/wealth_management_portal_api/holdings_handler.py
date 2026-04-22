"""Handler for holdings endpoint."""

from pydantic import BaseModel
from wealth_management_portal_portfolio_data_access.repositories.holdings_repository import (
    HoldingsRepository,
)

from .init import logger


class HoldingResponse(BaseModel):
    """Response model for holding data."""

    position_id: str
    portfolio_id: str
    security_id: str
    ticker: str
    company_name: str
    shares: float
    cost_basis: float
    current_price: float
    current_value: float
    unrealized_gain_loss: float
    as_of_date: str


class HoldingsListResponse(BaseModel):
    """Response model for holdings list."""

    holdings: list[HoldingResponse]


def get_client_holdings(client_id: str, limit: int = 20, offset: int = 0) -> HoldingsListResponse:
    """Get holdings for a specific client from Redshift."""
    try:
        logger.info("Fetching holdings for client: %s", client_id)
        repo = HoldingsRepository()

        holdings_data = repo.get_client_holdings(client_id, limit, offset)
        logger.info("Got %d holdings", len(holdings_data))

        holdings = []
        for holding in holdings_data:
            holdings.append(
                HoldingResponse(
                    position_id=str(holding.get("position_id", "")),
                    portfolio_id=str(holding.get("portfolio_id", "")),
                    security_id=str(holding.get("security_id", "")),
                    ticker=str(holding.get("ticker", "")),
                    company_name=str(holding.get("company_name", "")),
                    shares=float(holding.get("shares") or 0),
                    cost_basis=float(holding.get("cost_basis") or 0),
                    current_price=float(holding.get("current_price") or 0),
                    current_value=float(holding.get("current_value") or 0),
                    unrealized_gain_loss=float(holding.get("unrealized_gain_loss") or 0),
                    as_of_date=str(holding.get("as_of_date", "")),
                )
            )

        return HoldingsListResponse(holdings=holdings)

    except Exception:
        logger.exception("Error fetching holdings")
        return HoldingsListResponse(holdings=[])
