# Transformation layer: converts data-layer models to report-shaped models
import logging
import math
import re
from datetime import date, datetime, timedelta

from wealth_management_portal_report.models import (
    ActivityLevel,
    AssociatedAccount,
    CashFlow,
    ClientProfile,
    Communications,
    Email,
    Holding,
    IncomeExpenseAnalysis,
    MarketContext,
    MarketEvent,
    Meeting,
    PerformanceMetrics,
    Portfolio,
    Position,
    ProjectedCashFlow,
    ProjectedPortfolioValue,
    RiskProfile,
    ServiceModel,
    Sophistication,
    TargetAllocation,
)

logger = logging.getLogger(__name__)


class InteractionType:
    IN_PERSON = "In-Person"
    VIDEO = "Video"
    PHONE = "Phone"
    MEETING = "Meeting"
    CALL = "Call"
    EMAIL = "Email"


EQUITY_DIVIDEND_YIELD = 0.02
FIXED_INCOME_YIELD = 0.03

# Asset class synonym mapping for consistent naming
_ASSET_CLASS_SYNONYMS = {
    "Stocks": "Equity",
    "Bonds": "Fixed Income",
    "Bond": "Fixed Income",
    "Equities": "Equity",
    "Stock": "Equity",
}


def _normalise_asset_class(name: str) -> str:
    """Normalise asset class name using synonym mapping."""
    return _ASSET_CLASS_SYNONYMS.get(name, name)


def get_value(obj, key, default=None):
    if hasattr(obj, key):
        return getattr(obj, key)
    elif hasattr(obj, "get"):
        return obj.get(key, default)
    else:
        return default


def get_date_value(obj, key):
    value = get_value(obj, key)
    if isinstance(value, date):
        return value
    elif isinstance(value, str):
        return date.fromisoformat(value)
    else:
        return None


def build_client_profile(
    client: dict,
    restrictions: list[dict],
    accounts: list[dict],
    transactions: list[dict],
) -> ClientProfile:
    """Convert data-layer client + restrictions + accounts into a report ClientProfile."""

    # Derive AUM from account balances
    # Handle both dict and Pydantic model objects
    def get_balance(account):
        if hasattr(account, "current_balance"):
            return float(account.current_balance)
        balance = account.get("current_balance", 0)
        return float(balance) if balance else 0.0

    aum = float(sum(get_balance(a) for a in accounts))

    # Derive tax jurisdiction from state
    state = get_value(client, "state")
    tax_jurisdiction = f"US - {state}" if state else "US"

    # Derive activity level from transaction count over rolling 12 months
    cutoff = date.today() - timedelta(days=365)

    def get_transaction_date(t):
        txn_date = get_value(t, "transaction_date")
        if isinstance(txn_date, date):
            return txn_date
        elif isinstance(txn_date, str):
            return date.fromisoformat(txn_date)
        else:
            return date.min  # fallback for invalid dates

    recent_count = sum(1 for t in transactions if get_transaction_date(t) >= cutoff)
    if recent_count > 24:
        activity_level = ActivityLevel.HIGH
    elif recent_count >= 6:
        activity_level = ActivityLevel.MEDIUM
    else:
        activity_level = ActivityLevel.LOW

    return ClientProfile(
        client_id=get_value(client, "client_id"),
        names=[f"{get_value(client, 'client_first_name')} {get_value(client, 'client_last_name')}"],
        dates_of_birth=[get_date_value(client, "date_of_birth")] if get_date_value(client, "date_of_birth") else [],
        client_since=get_date_value(client, "client_since") or date.today(),
        aum=aum,
        risk_profile=(
            RiskProfile(get_value(client, "risk_tolerance"))
            if get_value(client, "risk_tolerance")
            else RiskProfile.MODERATE
        ),
        service_model=(
            ServiceModel(get_value(client, "service_model"))
            if get_value(client, "service_model")
            else ServiceModel.ADVISORY
        ),
        activity_level=activity_level,
        sophistication=(
            Sophistication(get_value(client, "sophistication"))
            if get_value(client, "sophistication")
            else Sophistication.INTERMEDIATE
        ),
        qualified_investor=get_value(client, "qualified_investor", False),
        domicile="US",  # TODO: derive from client data when international clients supported
        tax_jurisdiction=tax_jurisdiction,
        restrictions=list(dict.fromkeys(get_value(r, "restriction") for r in restrictions)),
        associated_accounts=[
            AssociatedAccount(
                account_type=get_value(a, "account_type"),
                value=get_balance(a),
                risk_profile=get_value(client, "risk_tolerance"),
                inception_date=get_date_value(a, "opening_date"),
            )
            for a in accounts
        ],
    )


def build_portfolio(
    holdings_with_securities: list[dict],
    performance_records: list[dict],
    transactions: list[dict],
    income_expense: dict | None,
    portfolio_record: dict | None = None,
) -> Portfolio:
    """Convert data-layer holdings, performance, transactions into a report Portfolio."""
    # Build positions from joined holdings + securities
    positions = []
    total_portfolio_value = (
        sum(float(h.get("market_value") or 0) for h in holdings_with_securities) or 1
    )  # avoid division by zero

    for h in holdings_with_securities:
        purchase_price = float(h["cost_basis"] / h["quantity"]) if h.get("quantity") and h.get("cost_basis") else 0.0
        current_price = float(h.get("current_price") or 0)
        market_value = float(h.get("market_value") or 0)

        # Calculate return_pct: (current_price - purchase_price) / purchase_price
        return_pct = None
        if purchase_price > 0:
            return_pct = (current_price - purchase_price) / purchase_price

        # Calculate portfolio_pct: market_value / total_portfolio_value
        portfolio_pct = market_value / total_portfolio_value

        # Parse inception_date from purchase_date or first_purchase_date if available
        inception_date = None
        for date_key in ["purchase_date", "first_purchase_date"]:
            if h.get(date_key):
                try:
                    if isinstance(h[date_key], str):
                        inception_date = date.fromisoformat(h[date_key])
                    elif isinstance(h[date_key], date):
                        inception_date = h[date_key]
                    break
                except (ValueError, TypeError):
                    continue

        # Normalise asset class for consistency with target allocation
        normalised_asset_class = _normalise_asset_class(h.get("asset_class") or "Other")

        positions.append(
            Position(
                ticker=h["ticker"],
                name=h["security_name"],
                quantity=float(h.get("quantity") or 0),
                purchase_price=purchase_price,
                current_price=current_price,
                market_value=market_value,
                unrealized_gain_loss=float(h.get("unrealized_gain_loss") or 0),
                asset_class=normalised_asset_class,
                return_pct=return_pct,
                portfolio_pct=portfolio_pct,
                volatility=h.get("volatility"),  # pass through if available
                inception_date=inception_date,
            )
        )

    # Aggregate holdings by normalised asset class for top-level holdings
    asset_totals: dict[str, float] = {}
    for h in holdings_with_securities:
        normalised_ac = _normalise_asset_class(h.get("asset_class") or "Other")
        asset_totals[normalised_ac] = asset_totals.get(normalised_ac, 0) + float(h.get("market_value") or 0)
    total_value = sum(asset_totals.values()) or 1  # avoid division by zero

    holdings = [Holding(asset=ac, allocation=val / total_value, value=val) for ac, val in asset_totals.items()]

    # Aggregate performance into summary metrics
    perf = _aggregate_performance(performance_records)

    # Group transactions into quarterly cash flows
    cash_flows = _build_cash_flows(transactions)

    # Income/expense analysis
    ie = IncomeExpenseAnalysis(
        monthly_income=float(get_value(income_expense, "monthly_income") or 0) if income_expense else 0,
        monthly_expenses=(float(get_value(income_expense, "monthly_expenses") or 0) if income_expense else 0),
        sustainability_years=(float(get_value(income_expense, "sustainability_years") or 0) if income_expense else 0),
    )

    target_allocation = _parse_target_allocation(
        portfolio_record.get("target_allocation") if portfolio_record else None
    )

    # Log warning for asset classes with no matching target allocation
    if target_allocation:
        target_asset_classes = {ta.asset for ta in target_allocation}
        for asset_class in asset_totals:
            if asset_class not in target_asset_classes:
                logger.warning("No target allocation found for asset class: %s", asset_class)

    projected_cash_flows = _build_projected_cash_flows(holdings, income_expense)
    return Portfolio(
        holdings=holdings,
        positions=positions,
        performance=perf,
        cash_flows=cash_flows,
        income_expense_analysis=ie,
        target_allocation=target_allocation,
        projected_cash_flows=projected_cash_flows,
        projected_portfolio_values=_build_projected_portfolio_values(
            holdings_with_securities, perf, projected_cash_flows
        ),
    )


def build_communications(interactions: list[dict]) -> Communications:
    """Convert data-layer interactions into report Communications."""

    meetings = [
        Meeting(
            date=get_date_value(i, "interaction_date"),
            meeting_type=get_value(i, "interaction_type"),
            subject=get_value(i, "subject") or "",
            notes=get_value(i, "summary") or "",
        )
        for i in interactions
        if get_value(i, "interaction_type")
        in (
            InteractionType.IN_PERSON,
            InteractionType.VIDEO,
            InteractionType.PHONE,
            InteractionType.MEETING,
            InteractionType.CALL,
        )
    ]
    emails = [
        Email(
            date=get_date_value(i, "interaction_date"),
            subject=get_value(i, "subject") or "",
            body=get_value(i, "summary") or "",
        )
        for i in interactions
        if get_value(i, "interaction_type") == InteractionType.EMAIL
    ]
    # Tasks are LLM-derived at report time, not from the data layer
    return Communications(meetings=meetings, emails=emails, tasks=[])


def build_market_context(
    themes: list[dict],
    as_of_date: date,
) -> MarketContext:
    """Convert data-layer themes into report MarketContext, sorted by rank ascending."""

    # Sentiment mapping: bullish -> Positive, bearish -> Negative, else -> Neutral
    _sentiment_map = {"bullish": "Positive", "bearish": "Negative"}

    # Sort by most recent first, then take top 10
    sorted_themes = sorted(
        themes,
        key=lambda t: get_value(t, "generated_at") or "",
        reverse=True,
    )[:10]

    return MarketContext(
        as_of_date=as_of_date,
        benchmark_returns=[],  # TODO: derive from performance benchmark data
        sector_performance=[],  # TODO: derive from securities + market_data
        notable_events=[
            MarketEvent(
                date=(
                    (
                        get_value(t, "generated_at").date()
                        if isinstance(get_value(t, "generated_at"), datetime)
                        else (
                            date.fromisoformat(get_value(t, "generated_at").split("T")[0])
                            if isinstance(get_value(t, "generated_at"), str)
                            else as_of_date
                        )
                    )
                    if get_value(t, "generated_at")
                    else as_of_date
                ),
                description=get_value(t, "title"),
                impact=_sentiment_map.get(get_value(t, "sentiment") or "", "Neutral"),
            )
            for t in sorted_themes
        ],
    )


def _parse_target_allocation(raw: str | None) -> list[TargetAllocation]:
    """Parse free-form allocation string, e.g. '70% Fixed Income, 30% Equity'."""
    if not raw:
        return []
    results = []
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*%\s*([^,]+)", raw):
        pct = float(match.group(1)) / 100
        asset = match.group(2).strip()
        # Normalise asset class name for consistency with holdings
        normalised_asset = _normalise_asset_class(asset)
        # ±5% bands as a reasonable default when not specified
        results.append(
            TargetAllocation(asset=normalised_asset, target=pct, lower_band=pct - 0.05, upper_band=pct + 0.05)
        )
    return results


def _build_projected_portfolio_values(
    positions: list,
    performance: PerformanceMetrics,
    projected_cash_flows: list,
) -> list[ProjectedPortfolioValue]:
    """Build projected portfolio values under base, conservative, and optimistic scenarios.

    Starting value = sum of all position market values
    Quarterly return (base) = performance.one_year / 4 (or performance.since_inception annualised / 4 as fallback)
    Conservative = base quarterly return - (volatility / sqrt(4)) (1 std dev down)
    Optimistic = base quarterly return + (volatility / sqrt(4)) (1 std dev up)
    For each quarter: apply return + net cash flow from projected_cash_flows
    Generate 4 quarters starting from the current quarter
    """
    # Calculate starting portfolio value
    starting_value = sum(float(p.get("market_value", 0)) for p in positions)
    if starting_value == 0:
        return []

    # Calculate base quarterly return
    base_quarterly_return = 0.0
    if performance.one_year and performance.one_year != 0:
        base_quarterly_return = performance.one_year / 4
    elif performance.since_inception and performance.since_inception != 0:
        # Annualize since_inception return (assume it's already annualized)
        base_quarterly_return = performance.since_inception / 4

    # Calculate portfolio-weighted volatility
    total_value = sum(float(p.get("market_value", 0)) for p in positions)
    portfolio_volatility = 0.0
    if total_value > 0:
        for p in positions:
            weight = float(p.get("market_value", 0)) / total_value
            vol = p.get("volatility", 0) or 0
            portfolio_volatility += weight * vol

    # Calculate quarterly volatility adjustment (1 std dev)
    quarterly_vol_adjustment = portfolio_volatility / math.sqrt(4) if portfolio_volatility > 0 else 0

    # Generate 4 quarters starting from current quarter
    today = date.today()
    current_q = (today.month - 1) // 3  # 0-indexed quarter (0–3)

    projected_values = []
    base_value = conservative_value = optimistic_value = starting_value

    for i in range(4):
        q_index = current_q + i
        year = today.year + q_index // 4
        quarter = q_index % 4 + 1
        period = f"{year}-Q{quarter}"

        # Find matching cash flow for this period
        net_cash_flow = 0.0
        for cf in projected_cash_flows:
            if cf.period == period:
                net_cash_flow = cf.known_inflows - cf.estimated_outflows
                break

        # Apply returns and cash flows
        base_value = base_value * (1 + base_quarterly_return) + net_cash_flow
        conservative_value = conservative_value * (1 + base_quarterly_return - quarterly_vol_adjustment) + net_cash_flow
        optimistic_value = optimistic_value * (1 + base_quarterly_return + quarterly_vol_adjustment) + net_cash_flow

        projected_values.append(
            ProjectedPortfolioValue(
                period=period,
                base=base_value,
                conservative=conservative_value,
                optimistic=optimistic_value,
            )
        )

    return projected_values


def _build_projected_cash_flows(
    holdings: list,
    income_expense: dict | None,
) -> list:
    """Project 4 quarters of cash flows from income/expense + estimated dividend yield.

    Yield estimates by asset class (annual, applied quarterly):
      - Equity / Stocks / *Equities: 2%
      - Fixed Income / Bonds: 3%
    """
    if not income_expense:
        return []

    # Estimate quarterly dividend income by asset class
    quarterly_dividends: float = 0.0
    dividend_breakdown: dict[str, float] = {}
    for h in holdings:
        asset = h.asset if hasattr(h, "asset") else h.get("asset_class", "Other")
        if any(k in asset for k in ("Equity", "Stock")):
            amt = h.value * EQUITY_DIVIDEND_YIELD / 4 if hasattr(h, "value") else 0
        elif any(k in asset for k in ("Fixed Income", "Bond")):
            amt = h.value * FIXED_INCOME_YIELD / 4 if hasattr(h, "value") else 0
        else:
            amt = 0
        if amt:
            dividend_breakdown[asset] = dividend_breakdown.get(asset, 0) + amt
            quarterly_dividends += amt

    quarterly_income = float(get_value(income_expense, "monthly_income") or 0) * 3
    quarterly_outflow = float(get_value(income_expense, "monthly_expenses") or 0) * 3

    # Generate next 4 quarters starting from the current quarter
    today = date.today()
    current_q = (today.month - 1) // 3  # 0-indexed quarter (0–3)
    projected = []
    for i in range(4):
        q_index = current_q + i
        year = today.year + q_index // 4
        quarter = q_index % 4 + 1
        projected.append(
            ProjectedCashFlow(
                period=f"{year}-Q{quarter}",
                known_inflows=quarterly_income + quarterly_dividends,
                estimated_outflows=quarterly_outflow,
                inflow_sources={
                    "income": quarterly_income,
                    "dividends": quarterly_dividends,
                    **{k: v for k, v in dividend_breakdown.items()},
                },
            )
        )
    return projected


def _aggregate_performance(records: list[dict]) -> PerformanceMetrics:
    """Aggregate period-level performance records into YTD, 1-year, and since-inception TWR.

    Uses time-weighted return chaining: (1+r1)*(1+r2)*...-1.
    Records must be ordered by period_start_date ascending.
    Volatility: annualised std dev of quarterly TWRs (annualisation factor sqrt(4)).
    Max drawdown: maximum peak-to-trough decline in cumulative return series.
    """

    if not records:
        return PerformanceMetrics(ytd=0, one_year=0, since_inception=0)

    today = date.today()
    ytd_cutoff = date(today.year, 1, 1)
    one_year_cutoff = today.replace(year=today.year - 1)

    def _chain(filtered: list[dict]) -> float:
        result = 1.0
        for r in filtered:
            twr = get_value(r, "time_weighted_return")
            result *= 1 + float(twr or 0)
        return result - 1

    # Annualised volatility from quarterly TWRs (sqrt(4) annualisation)
    twrs = [float(get_value(r, "time_weighted_return") or 0) for r in records]
    if len(twrs) >= 2:
        mean = sum(twrs) / len(twrs)
        variance = sum((r - mean) ** 2 for r in twrs) / (len(twrs) - 1)
        volatility = math.sqrt(variance) * math.sqrt(4)
    else:
        volatility = None

    # Max drawdown from cumulative return series
    if len(twrs) >= 2:
        cumulative = 1.0
        peak = 1.0
        max_dd = 0.0
        for r in twrs:
            cumulative *= 1 + r
            if cumulative > peak:
                peak = cumulative
            drawdown = (peak - cumulative) / peak
            if drawdown > max_dd:
                max_dd = drawdown
        max_drawdown = max_dd
    else:
        max_drawdown = None

    return PerformanceMetrics(
        ytd=_chain([r for r in records if get_date_value(r, "period_start_date") >= ytd_cutoff]),
        one_year=_chain([r for r in records if get_date_value(r, "period_start_date") >= one_year_cutoff]),
        since_inception=_chain(records),
        volatility=volatility,
        max_drawdown=max_drawdown,
    )


def _build_cash_flows(transactions: list[dict]) -> list[CashFlow]:
    """Group transactions into quarterly cash flows."""

    quarters: dict[str, dict[str, float]] = {}
    for t in transactions:
        transaction_date = get_date_value(t, "transaction_date")
        q = f"{transaction_date.year}-Q{(transaction_date.month - 1) // 3 + 1}"
        if q not in quarters:
            quarters[q] = {"inflows": 0, "outflows": 0}
        amount = float(get_value(t, "amount") or 0)
        transaction_type = get_value(t, "transaction_type")
        if transaction_type in ("Deposit", "Transfer In", "Dividend"):
            quarters[q]["inflows"] += amount
        else:
            quarters[q]["outflows"] += abs(amount)
    return [CashFlow(period=q, inflows=v["inflows"], outflows=v["outflows"]) for q, v in sorted(quarters.items())]
