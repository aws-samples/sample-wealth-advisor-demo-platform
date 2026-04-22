# Redshift-mirroring model for client interactions
from datetime import date

from pydantic import BaseModel


class Interaction(BaseModel):
    """Interaction record from Redshift interactions table."""

    interaction_id: str
    client_id: str
    advisor_id: str
    interaction_type: str
    interaction_date: date
    subject: str | None = None
    summary: str | None = None
    sentiment: str | None = None
    duration_minutes: int | None = None
