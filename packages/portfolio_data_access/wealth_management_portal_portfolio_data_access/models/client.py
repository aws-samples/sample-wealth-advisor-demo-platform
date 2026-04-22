# Redshift-mirroring models for clients and investment restrictions
from datetime import date

from pydantic import BaseModel


class Client(BaseModel):
    """Client record from Redshift clients table."""

    client_id: str
    client_first_name: str
    client_last_name: str
    email: str
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    date_of_birth: date | None = None
    risk_tolerance: str | None = None
    investment_objectives: str | None = None
    segment: str | None = None
    status: str = "Active"
    advisor_id: str
    client_since: date | None = None
    service_model: str | None = None
    sophistication: str | None = None
    qualified_investor: bool = False


class ClientRestriction(BaseModel):
    """Investment restriction from Redshift client_investment_restrictions table."""

    restriction_id: str
    client_id: str
    restriction: str
    created_date: date | None = None
