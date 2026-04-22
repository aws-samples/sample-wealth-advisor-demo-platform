# Portfolio data contract

from datetime import date

from pydantic import BaseModel


class Position(BaseModel):
    """Individual security/holding in the portfolio."""

    ticker: str
    name: str
    quantity: float
    purchase_price: float
    current_price: float
    market_value: float
    unrealized_gain_loss: float
    asset_class: str
    # New optional fields for per-position metrics
    return_pct: float | None = None  # total return % since purchase
    portfolio_pct: float | None = None  # % of total portfolio value
    volatility: float | None = None  # position-level volatility if available
    inception_date: date | None = None  # when the position was first acquired


class Holding(BaseModel):
    """
    Single position in the portfolio.
    Represents an asset class or security with its allocation and current value.
    """

    asset: str
    allocation: float  # percentage, e.g., 0.35 for 35%
    value: float


class PerformanceMetrics(BaseModel):
    """
    Portfolio returns over standard time periods.
    All values are percentages, e.g., 0.08 for 8%.
    """

    ytd: float
    one_year: float
    since_inception: float
    volatility: float | None = None  # annualized standard deviation, e.g., 0.09 for 9%
    max_drawdown: float | None = None  # worst peak-to-trough decline, e.g., -0.12 for -12%


class CashFlow(BaseModel):
    """
    Money movement for a specific period.
    Tracks deposits (inflows) and withdrawals (outflows).
    """

    period: str  # e.g., "2024-Q4", "2025-01"
    inflows: float
    outflows: float


class IncomeExpenseAnalysis(BaseModel):
    """
    Sustainability assessment of current spending pattern.
    Projects how long the portfolio can support current cash flow rate.
    """

    monthly_income: float
    monthly_expenses: float
    sustainability_years: float  # how long current pattern can last


class TargetAllocation(BaseModel):
    """Strategic asset allocation target with permitted deviation bands."""

    asset: str
    target: float  # target percentage, e.g., 0.35 for 35%
    lower_band: float  # minimum permitted, e.g., 0.30
    upper_band: float  # maximum permitted, e.g., 0.40


class ProjectedCashFlow(BaseModel):
    """Forward-looking cash flow estimate for a future period."""

    period: str  # e.g., "2025-Q1"
    known_inflows: float  # dividends, interest, scheduled deposits
    estimated_outflows: float  # based on historical withdrawal patterns
    inflow_sources: dict[str, float] = {}  # breakdown by source: dividends, interest, coupons, etc.


class ProjectedPortfolioValue(BaseModel):
    """Projected portfolio value under different scenarios for a future period."""

    period: str  # e.g., "2026-Q1"
    base: float
    conservative: float
    optimistic: float


class Portfolio(BaseModel):
    """
    Complete portfolio state and analytics.
    Combines holdings, performance, cash flows, and sustainability projections.
    """

    holdings: list[Holding]
    positions: list[Position] = []  # individual security-level holdings
    performance: PerformanceMetrics
    cash_flows: list[CashFlow]
    income_expense_analysis: IncomeExpenseAnalysis
    target_allocation: list[TargetAllocation] = []  # strategic asset allocation reference
    projected_cash_flows: list[ProjectedCashFlow] = []  # forward-looking cash flow estimates
    projected_portfolio_values: list[ProjectedPortfolioValue] = []  # projected portfolio values under scenarios
