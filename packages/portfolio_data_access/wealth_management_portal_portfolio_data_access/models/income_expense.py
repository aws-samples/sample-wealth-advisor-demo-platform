# Redshift-mirroring model for client income and expenses
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class ClientIncomeExpense(BaseModel):
    """Income/expense record from Redshift client_income_expense table. Composite PK: (client_id, as_of_date)."""

    client_id: str
    as_of_date: date
    monthly_income: Decimal
    monthly_expenses: Decimal
    sustainability_years: Decimal
