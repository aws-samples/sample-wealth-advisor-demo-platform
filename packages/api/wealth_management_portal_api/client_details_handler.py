"""Handler for client details."""

from pydantic import BaseModel
from wealth_management_portal_portfolio_data_access.repositories.client_details_repository import (
    ClientDetailsRepository,
)

from .init import logger


class ClientDetailsResponse(BaseModel):
    """Response model for client details."""

    client_id: str
    customer_name: str
    email: str
    phone: str
    segment: str
    risk_tolerance: str
    aum: float
    interaction_sentiment: str
    client_city: str
    client_state: str
    client_created_date: str


def get_client_details(client_id: str) -> ClientDetailsResponse:
    """Get complete client details from Redshift."""
    try:
        repo = ClientDetailsRepository()
        data = repo.get_client_details(client_id)

        if not data:
            return ClientDetailsResponse(
                client_id=client_id,
                customer_name="Unknown",
                email="",
                phone="",
                segment="",
                risk_tolerance="",
                aum=0.0,
                interaction_sentiment="",
                client_city="",
                client_state="",
                client_created_date="",
            )

        return ClientDetailsResponse(
            client_id=str(data.get("client_id") or client_id),
            customer_name=str(data.get("customer_name") or ""),
            email=str(data.get("email") or ""),
            phone=str(data.get("phone") or ""),
            segment=str(data.get("segment") or ""),
            risk_tolerance=str(data.get("risk_tolerance") or ""),
            aum=float(data.get("total_current_value") or 0),
            interaction_sentiment=str(data.get("interaction_sentiment") or ""),
            client_city=str(data.get("client_city") or ""),
            client_state=str(data.get("client_state") or ""),
            client_created_date=str(data.get("client_created_date") or ""),
        )
    except Exception:
        logger.exception("Error fetching client details")
        return ClientDetailsResponse(
            client_id=client_id,
            customer_name="Unknown",
            email="",
            phone="",
            segment="",
            risk_tolerance="",
            aum=0.0,
            interaction_sentiment="",
            client_city="",
            client_state="",
            client_created_date="",
        )
