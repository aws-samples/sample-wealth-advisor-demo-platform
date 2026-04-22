# Redshift-mirroring models for portfolios, holdings, and securities
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class PortfolioRecord(BaseModel):
    """Portfolio record from Redshift portfolios table."""

    portfolio_id: str
    account_id: str
    portfolio_name: str
    investment_model: str | None = None
    target_allocation: str | None = None
    benchmark: str | None = None
    inception_date: date


class Holding(BaseModel):
    """Holding record from Redshift holdings table."""

    position_id: str
    portfolio_id: str
    security_id: str
    quantity: Decimal | None = None
    cost_basis: Decimal | None = None
    current_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_gain_loss: Decimal | None = None
    as_of_date: date


class Security(BaseModel):
    """Security record from Redshift securities table."""

    security_id: str
    ticker: str
    security_name: str
    security_type: str
    asset_class: str | None = None
    sector: str | None = None
    current_price: Decimal | None = None
    price_date: date | None = None
