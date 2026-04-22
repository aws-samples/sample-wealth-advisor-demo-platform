# Redshift-mirroring model for accounts
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class Account(BaseModel):
    """Account record from Redshift accounts table."""

    account_id: str
    client_id: str
    account_type: str
    account_name: str
    opening_date: date
    investment_strategy: str | None = None
    status: str = "Active"
    current_balance: Decimal = Decimal("0")
