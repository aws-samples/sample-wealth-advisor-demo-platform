"""Handler for client list endpoint."""

from datetime import datetime

from pydantic import BaseModel
from wealth_management_portal_portfolio_data_access.repositories.client_repository import (
    ClientRepository,
)

from .init import logger


class ClientResponse(BaseModel):
    """Response model for client data."""

    client_id: str
    customer_name: str
    segment: str
    aum: float
    net_worth: float
    ytd_perf: float
    goal_progress: float
    risk_tolerance: str
    client_since: str
    interaction_sentiment: str
    next_best_action: str | None = None


class ClientListResponse(BaseModel):
    """Response model for client list."""

    clients: list[ClientResponse]


def get_clients(limit: int = 50, offset: int = 0) -> ClientListResponse:
    """Get all clients from Redshift."""
    try:
        logger.info("Fetching clients", extra={"limit": limit, "offset": offset})
        repo = ClientRepository()

        clients_data = repo.get_all_clients(limit, offset)
        logger.info("Got %d clients", len(clients_data))

        clients = []
        for client in clients_data:
            # Calculate years since client created
            if client.get("client_created_date"):
                created_date = datetime.fromisoformat(str(client["client_created_date"]))
                years_since = (datetime.now() - created_date).days / 365.25
                client_since = f"{years_since:.1f} years"
            else:
                client_since = "N/A"

            clients.append(
                ClientResponse(
                    client_id=str(client.get("client_id", "")),
                    customer_name=f"{client.get('client_first_name', '')} {client.get('client_last_name', '')}".strip(),
                    segment=str(client.get("client_segment", "")),
                    aum=float(client.get("aum") or 0),
                    net_worth=float(client.get("total_current_value") or 0),
                    ytd_perf=0.0,
                    goal_progress=float(client.get("goals_on_track") or 0),
                    risk_tolerance=str(client.get("risk_tolerance", "")),
                    client_since=client_since,
                    interaction_sentiment=str(client.get("interaction_sentiment") or ""),
                    next_best_action=client.get("next_best_action") or None,
                )
            )

        return ClientListResponse(clients=clients)

    except Exception:
        logger.exception("Error fetching clients")
        return ClientListResponse(clients=[])
