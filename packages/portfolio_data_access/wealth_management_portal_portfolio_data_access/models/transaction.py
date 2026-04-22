# Redshift-mirroring model for transactions
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class Transaction(BaseModel):
    """Transaction record from Redshift transactions table."""

    transaction_id: str
    account_id: str
    security_id: str | None = None
    transaction_type: str
    transaction_date: date
    settlement_date: date | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    amount: Decimal | None = None
    status: str
