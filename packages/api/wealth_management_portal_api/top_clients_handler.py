"""Handler for top clients endpoint."""

from datetime import datetime

from pydantic import BaseModel
from wealth_management_portal_portfolio_data_access.repositories.client_repository import (
    ClientRepository,
)

from .init import logger


class TopClient(BaseModel):
    """Model for a top client."""

    client_id: str
    name: str
    aum: float
    ytd_performance: float
    client_since: str
    client_sentiment: str
    next_best_action: str | None = None


class TopClientsResponse(BaseModel):
    """Response model for top clients."""

    clients: list[TopClient]


def get_top_clients() -> TopClientsResponse:
    """Get top 5 clients by net worth."""
    try:
        repo = ClientRepository()
        clients = repo.get_all_clients(limit=50, offset=0)

        top_clients = []
        for client in clients:
            if client.get("client_created_date"):
                created_date = datetime.fromisoformat(str(client["client_created_date"]))
                years_since = (datetime.now() - created_date).days / 365.25
                client_since = f"{years_since:.1f} years"
            else:
                client_since = "N/A"

            top_clients.append(
                TopClient(
                    client_id=client["client_id"],
                    name=f"{client.get('client_first_name', '')} {client.get('client_last_name', '')}".strip(),
                    aum=float(client.get("aum") or client.get("total_current_value") or 0),
                    ytd_performance=float(client.get("time_weighted_return") or 0),
                    client_since=client_since,
                    client_sentiment=str(client.get("interaction_sentiment") or ""),
                    next_best_action=client.get("next_best_action") or None,
                )
            )

        # Sort by AUM descending
        top_clients.sort(key=lambda c: c.aum, reverse=True)

        return TopClientsResponse(clients=top_clients[:5])

    except Exception:
        logger.exception("Error fetching top clients")
        return TopClientsResponse(clients=[])
