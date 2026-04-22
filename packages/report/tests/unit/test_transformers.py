"""Unit tests for transformers module."""

from datetime import date

import pytest

from wealth_management_portal_report.models import ActivityLevel, RiskProfile, ServiceModel
from wealth_management_portal_report.transformers import (
    _aggregate_performance,
    _build_cash_flows,
    _build_projected_cash_flows,
    _parse_target_allocation,
    build_client_profile,
    build_communications,
    build_market_context,
    build_portfolio,
)


def test_build_client_profile_basic():
    """Test basic client profile building with client, restrictions, and accounts."""
    client = {
        "client_id": "client1",
        "client_first_name": "John",
        "client_last_name": "Doe",
        "email": "john@example.com",
        "state": "CA",
        "risk_tolerance": "Aggressive",
        "service_model": "Discretionary",
        "advisor_id": "advisor1",
    }

    restrictions = [
        {"restriction_id": "r1", "client_id": "client1", "restriction": "No tobacco"},
        {"restriction_id": "r2", "client_id": "client1", "restriction": "ESG only"},
    ]

    accounts = [
        {
            "account_id": "acc1",
            "client_id": "client1",
            "account_type": "Taxable",
            "account_name": "Main",
            "opening_date": "2020-01-01",
            "current_balance": 100000,
        },
        {
            "account_id": "acc2",
            "client_id": "client1",
            "account_type": "IRA",
            "account_name": "Retirement",
            "opening_date": "2019-01-01",
            "current_balance": 250000,
        },
    ]

    profile = build_client_profile(client, restrictions, accounts, [])

    assert profile.names == ["John Doe"]
    assert profile.aum == 350000.0
    assert profile.restrictions == ["No tobacco", "ESG only"]
    assert len(profile.associated_accounts) == 2
    assert profile.tax_jurisdiction == "US - CA"
    assert profile.risk_profile == RiskProfile.AGGRESSIVE
    assert profile.service_model == ServiceModel.DISCRETIONARY


def test_build_client_profile_defaults():
    """Test client profile with defaults when optional fields are missing."""
    client = {
        "client_id": "client2",
        "client_first_name": "Jane",
        "client_last_name": "Smith",
        "email": "jane@example.com",
        "advisor_id": "advisor1",
    }

    profile = build_client_profile(client, [], [], [])

    assert profile.tax_jurisdiction == "US"
    assert profile.risk_profile == RiskProfile.MODERATE
    assert profile.service_model == ServiceModel.ADVISORY


def test_build_portfolio_positions():
    """Test portfolio positions building from holdings with securities."""
    holdings_with_securities = [
        {
            "ticker": "AAPL",
            "security_name": "Apple Inc",
            "quantity": 100,
            "cost_basis": 15000,
            "current_price": 180.0,
            "market_value": 18000.0,
            "unrealized_gain_loss": 3000.0,
            "asset_class": "Equity",
        },
        {
            "ticker": "GOOGL",
            "security_name": "Alphabet Inc",
            "quantity": 50,
            "cost_basis": 10000,
            "current_price": 2500.0,
            "market_value": 125000.0,
            "unrealized_gain_loss": 115000.0,
            "asset_class": "Equity",
        },
        {
            "ticker": "BND",
            "security_name": "Vanguard Total Bond Market",
            "quantity": 1000,
            "cost_basis": 80000,
            "current_price": 82.0,
            "market_value": 82000.0,
            "unrealized_gain_loss": 2000.0,
            "asset_class": "Fixed Income",
        },
    ]

    portfolio = build_portfolio(holdings_with_securities, [], [], None)

    assert len(portfolio.positions) == 3

    aapl_pos = next(p for p in portfolio.positions if p.ticker == "AAPL")
    assert aapl_pos.name == "Apple Inc"
    assert aapl_pos.asset_class == "Equity"
    assert aapl_pos.purchase_price == 150.0  # 15000 / 100

    googl_pos = next(p for p in portfolio.positions if p.ticker == "GOOGL")
    assert googl_pos.purchase_price == 200.0  # 10000 / 50

    bnd_pos = next(p for p in portfolio.positions if p.ticker == "BND")
    assert bnd_pos.purchase_price == 80.0  # 80000 / 1000


def test_build_portfolio_holdings_aggregation():
    """Test portfolio holdings aggregation by asset class."""
    holdings_with_securities = [
        {
            "ticker": "AAPL",
            "security_name": "Apple Inc",
            "market_value": 100000.0,
            "asset_class": "Equity",
        },
        {
            "ticker": "MSFT",
            "security_name": "Microsoft Corp",
            "market_value": 150000.0,
            "asset_class": "Equity",
        },
        {
            "ticker": "BND",
            "security_name": "Vanguard Total Bond Market",
            "market_value": 50000.0,
            "asset_class": "Fixed Income",
        },
    ]

    portfolio = build_portfolio(holdings_with_securities, [], [], None)

    assert len(portfolio.holdings) == 2

    equity_holding = next(h for h in portfolio.holdings if h.asset == "Equity")
    assert equity_holding.value == 250000.0
    assert equity_holding.allocation == 250000.0 / 300000.0  # 83.33%

    bond_holding = next(h for h in portfolio.holdings if h.asset == "Fixed Income")
    assert bond_holding.value == 50000.0
    assert bond_holding.allocation == 50000.0 / 300000.0  # 16.67%


def test_build_portfolio_income_expense():
    """Test portfolio with income expense analysis."""
    income_expense = {
        "client_id": "client1",
        "as_of_date": "2024-01-01",
        "monthly_income": 10000,
        "monthly_expenses": 8000,
        "sustainability_years": 25,
    }

    portfolio = build_portfolio([], [], [], income_expense)

    assert portfolio.income_expense_analysis.monthly_income == 10000.0
    assert portfolio.income_expense_analysis.monthly_expenses == 8000.0
    assert portfolio.income_expense_analysis.sustainability_years == 25.0


def test_build_portfolio_no_income_expense():
    """Test portfolio with no income expense data."""
    portfolio = build_portfolio([], [], [], None)

    assert portfolio.income_expense_analysis.monthly_income == 0
    assert portfolio.income_expense_analysis.monthly_expenses == 0
    assert portfolio.income_expense_analysis.sustainability_years == 0


def test_build_communications_splits_by_type():
    """Test communications splitting interactions by type."""
    interactions = [
        {
            "interaction_id": "i1",
            "client_id": "client1",
            "advisor_id": "advisor1",
            "interaction_type": "In-Person",
            "interaction_date": "2024-01-15",
            "subject": "Quarterly Review",
            "summary": "Discussed portfolio performance",
        },
        {
            "interaction_id": "i2",
            "client_id": "client1",
            "advisor_id": "advisor1",
            "interaction_type": "Phone",
            "interaction_date": "2024-01-20",
            "subject": "Market Update",
            "summary": "Called about market volatility",
        },
        {
            "interaction_id": "i3",
            "client_id": "client1",
            "advisor_id": "advisor1",
            "interaction_type": "Email",
            "interaction_date": "2024-01-25",
            "subject": "Document Request",
            "summary": "Sent tax documents",
        },
    ]

    comms = build_communications(interactions)

    assert len(comms.meetings) == 2
    assert len(comms.emails) == 1
    assert len(comms.tasks) == 0

    assert comms.meetings[0].meeting_type == "In-Person"
    assert comms.meetings[1].meeting_type == "Phone"
    assert comms.emails[0].subject == "Document Request"


def test_build_communications_empty():
    """Test communications with empty interactions list."""
    comms = build_communications([])

    assert len(comms.meetings) == 0
    assert len(comms.emails) == 0
    assert len(comms.tasks) == 0


def test_build_market_context_sentiment_mapping():
    """Test sentiment mapping: bullish->Positive, bearish->Negative, None->Neutral."""
    themes = [
        {
            "theme_id": "t1",
            "client_id": "c1",
            "title": "Bull Run",
            "sentiment": "bullish",
            "rank": 1,
            "generated_at": "2024-01-15",
        },
        {
            "theme_id": "t2",
            "client_id": "c1",
            "title": "Bear Market",
            "sentiment": "bearish",
            "rank": 2,
            "generated_at": "2024-01-20",
        },
        {
            "theme_id": "t3",
            "client_id": "c1",
            "title": "Sideways",
            "sentiment": None,
            "rank": 3,
            "generated_at": "2024-01-25",
        },
    ]

    as_of_date = date(2024, 2, 1)
    context = build_market_context(themes, as_of_date)

    assert context.as_of_date == as_of_date
    assert len(context.notable_events) == 3
    # Sorted by generated_at descending: Sideways (Jan 25), Bear (Jan 20), Bull (Jan 15)
    assert context.notable_events[0].impact == "Neutral"
    assert context.notable_events[1].impact == "Negative"
    assert context.notable_events[2].impact == "Positive"


def test_build_market_context_rank_ordering():
    """Test themes are ordered by generated_at descending in output."""
    themes = [
        {"theme_id": "t3", "client_id": "c1", "title": "Third", "rank": 3, "generated_at": "2024-01-10"},
        {"theme_id": "t1", "client_id": "c1", "title": "First", "rank": 1, "generated_at": "2024-01-30"},
        {"theme_id": "t2", "client_id": "c1", "title": "Second", "rank": 2, "generated_at": "2024-01-20"},
    ]

    context = build_market_context(themes, date(2024, 2, 1))

    assert [e.description for e in context.notable_events] == ["First", "Second", "Third"]


def test_build_market_context_none_generated_at_fallback():
    """Test generated_at=None falls back to as_of_date."""
    themes = [{"theme_id": "t1", "client_id": "c1", "title": "No Date", "generated_at": None}]
    as_of_date = date(2024, 2, 1)

    context = build_market_context(themes, as_of_date)

    assert context.notable_events[0].date == as_of_date


def test_build_cash_flows_quarterly_grouping():
    """Test cash flows quarterly grouping from transactions."""
    transactions = [
        {
            "transaction_id": "t1",
            "account_id": "acc1",
            "transaction_type": "Deposit",
            "transaction_date": "2024-01-15",
            "amount": 10000,
            "status": "Settled",
        },
        {
            "transaction_id": "t2",
            "account_id": "acc1",
            "transaction_type": "Withdrawal",
            "transaction_date": "2024-02-10",
            "amount": 5000,
            "status": "Settled",
        },
        {
            "transaction_id": "t3",
            "account_id": "acc1",
            "transaction_type": "Dividend",
            "transaction_date": "2024-03-20",
            "amount": 2000,
            "status": "Settled",
        },
        {
            "transaction_id": "t4",
            "account_id": "acc1",
            "transaction_type": "Transfer In",
            "transaction_date": "2024-04-05",
            "amount": 15000,
            "status": "Settled",
        },
        {
            "transaction_id": "t5",
            "account_id": "acc1",
            "transaction_type": "Sale",
            "transaction_date": "2024-05-10",
            "amount": 8000,
            "status": "Settled",
        },
    ]

    cash_flows = _build_cash_flows(transactions)

    assert len(cash_flows) == 2

    q1_flow = next(cf for cf in cash_flows if cf.period == "2024-Q1")
    assert q1_flow.inflows == 12000.0  # 10000 + 2000
    assert q1_flow.outflows == 5000.0

    q2_flow = next(cf for cf in cash_flows if cf.period == "2024-Q2")
    assert q2_flow.inflows == 15000.0
    assert q2_flow.outflows == 8000.0


def test_aggregate_performance_empty():
    """Test performance aggregation with empty records."""
    perf = _aggregate_performance([])

    assert perf.ytd == 0
    assert perf.one_year == 0
    assert perf.since_inception == 0


def test_aggregate_performance_chains_twr():
    """TWR is chained across periods, not just the latest record."""
    records = [
        {
            "performance_id": "p1",
            "portfolio_id": "port1",
            "period": "2023-Q4",
            "period_start_date": "2023-10-01",
            "period_end_date": "2023-12-31",
            "time_weighted_return": 0.05,
        },
        {
            "performance_id": "p2",
            "portfolio_id": "port1",
            "period": "2024-Q1",
            "period_start_date": "2024-01-01",
            "period_end_date": "2024-03-31",
            "time_weighted_return": 0.03,
        },
    ]
    perf = _aggregate_performance(records)
    # since_inception = (1.05 * 1.03) - 1 = 0.0815
    assert perf.since_inception == pytest.approx(0.0815)


def test_aggregate_performance_ytd_excludes_prior_year():
    """YTD only chains records from Jan 1 of the current year."""
    records = [
        {
            "performance_id": "p1",
            "portfolio_id": "port1",
            "period": "2023-Q4",
            "period_start_date": "2023-10-01",
            "period_end_date": "2023-12-31",
            "time_weighted_return": 0.10,
        },
        {
            "performance_id": "p2",
            "portfolio_id": "port1",
            "period": "2024-Q1",
            "period_start_date": "2024-01-01",
            "period_end_date": "2024-03-31",
            "time_weighted_return": 0.04,
        },
    ]
    perf = _aggregate_performance(records)
    # YTD should only include the 2024-Q1 record (or later), not the 2023 one
    assert perf.ytd != perf.since_inception
    assert perf.since_inception == pytest.approx((1.10 * 1.04) - 1)


def test_parse_target_allocation_two_way():
    """Standard two-asset allocation string parses correctly."""
    result = _parse_target_allocation("70% Fixed Income, 30% Equity")
    assert len(result) == 2
    fi = next(r for r in result if r.asset == "Fixed Income")
    eq = next(r for r in result if r.asset == "Equity")
    assert fi.target == pytest.approx(0.70)
    assert eq.target == pytest.approx(0.30)
    assert fi.lower_band == pytest.approx(0.65)
    assert fi.upper_band == pytest.approx(0.75)


def test_parse_target_allocation_three_way():
    """Three-asset allocation string parses all three entries."""
    result = _parse_target_allocation("85% Stocks, 10% Alternatives, 5% Cash")
    assert len(result) == 3
    assert next(r for r in result if r.asset == "Equity").target == pytest.approx(0.85)


def test_parse_target_allocation_none():
    """None input returns empty list."""
    assert _parse_target_allocation(None) == []


def test_build_portfolio_target_allocation():
    """build_portfolio passes target_allocation through from PortfolioRecord."""
    record = {
        "portfolio_id": "p1",
        "account_id": "a1",
        "portfolio_name": "Main",
        "inception_date": "2020-01-01",
        "target_allocation": "60% Equity, 40% Fixed Income",
    }
    portfolio = build_portfolio([], [], [], None, record)
    assert len(portfolio.target_allocation) == 2


def test_build_client_profile_activity_high():
    """More than 24 transactions in last 12 months → HIGH."""
    client = {
        "client_id": "c1",
        "client_first_name": "A",
        "client_last_name": "B",
        "email": "a@b.com",
        "advisor_id": "adv1",
    }
    transactions = [
        {
            "transaction_id": f"t{i}",
            "account_id": "acc1",
            "transaction_type": "Deposit",
            "transaction_date": date.today().isoformat(),
            "amount": 100,
            "status": "Settled",
        }
        for i in range(25)
    ]
    profile = build_client_profile(client, [], [], transactions)
    assert profile.activity_level == ActivityLevel.HIGH


def test_build_client_profile_activity_medium():
    """6–24 transactions in last 12 months → MEDIUM."""
    client = {
        "client_id": "c1",
        "client_first_name": "A",
        "client_last_name": "B",
        "email": "a@b.com",
        "advisor_id": "adv1",
    }
    transactions = [
        {
            "transaction_id": f"t{i}",
            "account_id": "acc1",
            "transaction_type": "Deposit",
            "transaction_date": date.today().isoformat(),
            "amount": 100,
            "status": "Settled",
        }
        for i in range(10)
    ]
    profile = build_client_profile(client, [], [], transactions)
    assert profile.activity_level == ActivityLevel.MEDIUM


def test_build_client_profile_activity_low():
    """Fewer than 6 transactions in last 12 months → LOW."""
    client = {
        "client_id": "c1",
        "client_first_name": "A",
        "client_last_name": "B",
        "email": "a@b.com",
        "advisor_id": "adv1",
    }
    transactions = [
        {
            "transaction_id": f"t{i}",
            "account_id": "acc1",
            "transaction_type": "Deposit",
            "transaction_date": date.today().isoformat(),
            "amount": 100,
            "status": "Settled",
        }
        for i in range(3)
    ]
    profile = build_client_profile(client, [], [], transactions)
    assert profile.activity_level == ActivityLevel.LOW


def test_build_client_profile_activity_excludes_old_transactions():
    """Transactions older than 12 months are excluded from the count."""
    client = {
        "client_id": "c1",
        "client_first_name": "A",
        "client_last_name": "B",
        "email": "a@b.com",
        "advisor_id": "adv1",
    }
    # 30 old transactions — should not count
    transactions = [
        {
            "transaction_id": f"t{i}",
            "account_id": "acc1",
            "transaction_type": "Deposit",
            "transaction_date": "2020-01-01",
            "amount": 100,
            "status": "Settled",
        }
        for i in range(30)
    ]
    profile = build_client_profile(client, [], [], transactions)
    assert profile.activity_level == ActivityLevel.LOW


def test_projected_cash_flows_no_income_expense():
    """No income/expense data → empty list."""
    assert _build_projected_cash_flows([], None) == []


def test_projected_cash_flows_four_quarters():
    """Returns exactly 4 quarters."""
    from wealth_management_portal_report.models import Holding

    holdings = [Holding(asset="Equity", allocation=1.0, value=100_000.0)]
    ie = {
        "client_id": "c1",
        "as_of_date": "2024-01-01",
        "monthly_income": 5000,
        "monthly_expenses": 4000,
        "sustainability_years": 20,
    }
    result = _build_projected_cash_flows(holdings, ie)
    assert len(result) == 4
    assert all(r.period.startswith("20") for r in result)


def test_projected_cash_flows_inflow_sources():
    """Inflow sources include income and dividends keys."""
    from wealth_management_portal_report.models import Holding

    holdings = [Holding(asset="Fixed Income", allocation=1.0, value=200_000.0)]
    ie = {
        "client_id": "c1",
        "as_of_date": "2024-01-01",
        "monthly_income": 3000,
        "monthly_expenses": 2000,
        "sustainability_years": 30,
    }
    result = _build_projected_cash_flows(holdings, ie)
    assert "income" in result[0].inflow_sources
    assert "dividends" in result[0].inflow_sources
    assert result[0].inflow_sources["dividends"] == pytest.approx(200_000 * 0.03 / 4)


def test_build_client_profile_deduplicates_restrictions():
    """Duplicate restriction rows from Redshift are deduplicated in the profile."""
    client = {
        "client_id": "c1",
        "client_first_name": "A",
        "client_last_name": "B",
        "email": "a@b.com",
        "advisor_id": "adv1",
    }
    restrictions = [
        {"restriction_id": "r1", "client_id": "c1", "restriction": "ESG only"},
        {"restriction_id": "r2", "client_id": "c1", "restriction": "ESG only"},
        {"restriction_id": "r3", "client_id": "c1", "restriction": "No leveraged ETFs"},
    ]
    profile = build_client_profile(client, restrictions, [], [])
    assert profile.restrictions == ["ESG only", "No leveraged ETFs"]


def test_build_portfolio_calculates_return_pct():
    """Position return_pct is calculated as (current_price - purchase_price) / purchase_price."""
    holdings_with_securities = [
        {
            "ticker": "AAPL",
            "security_name": "Apple Inc",
            "quantity": 100,
            "cost_basis": 15000,
            "current_price": 180.0,
            "market_value": 18000.0,
            "unrealized_gain_loss": 3000.0,
            "asset_class": "Equity",
        },
    ]

    portfolio = build_portfolio(holdings_with_securities, [], [], None)

    aapl_pos = next(p for p in portfolio.positions if p.ticker == "AAPL")
    # purchase_price = 15000 / 100 = 150, current_price = 180
    # return_pct = (180 - 150) / 150 = 0.2 (20%)
    assert aapl_pos.return_pct == pytest.approx(0.2)


def test_build_portfolio_calculates_portfolio_pct():
    """Position portfolio_pct is calculated as market_value / total_portfolio_value."""
    holdings_with_securities = [
        {
            "ticker": "AAPL",
            "security_name": "Apple Inc",
            "quantity": 100,
            "cost_basis": 15000,
            "current_price": 180.0,
            "market_value": 18000.0,
            "unrealized_gain_loss": 3000.0,
            "asset_class": "Equity",
        },
        {
            "ticker": "GOOGL",
            "security_name": "Alphabet Inc",
            "quantity": 50,
            "cost_basis": 10000,
            "current_price": 2500.0,
            "market_value": 125000.0,
            "unrealized_gain_loss": 115000.0,
            "asset_class": "Equity",
        },
    ]

    portfolio = build_portfolio(holdings_with_securities, [], [], None)

    aapl_pos = next(p for p in portfolio.positions if p.ticker == "AAPL")
    googl_pos = next(p for p in portfolio.positions if p.ticker == "GOOGL")

    assert aapl_pos.portfolio_pct == pytest.approx(18000.0 / 143000.0)
    assert googl_pos.portfolio_pct == pytest.approx(125000.0 / 143000.0)


def test_build_portfolio_handles_zero_purchase_price():
    """Position with zero purchase_price gets return_pct = None."""
    holdings_with_securities = [
        {
            "ticker": "FREE",
            "security_name": "Free Stock",
            "quantity": 100,
            "cost_basis": 0,
            "current_price": 50.0,
            "market_value": 5000.0,
            "unrealized_gain_loss": 5000.0,
            "asset_class": "Equity",
        },
    ]

    portfolio = build_portfolio(holdings_with_securities, [], [], None)

    free_pos = next(p for p in portfolio.positions if p.ticker == "FREE")
    assert free_pos.return_pct is None


def test_build_portfolio_passes_inception_date():
    """Position inception_date is passed from holdings data purchase_date field."""
    holdings_with_securities = [
        {
            "ticker": "AAPL",
            "security_name": "Apple Inc",
            "quantity": 100,
            "cost_basis": 15000,
            "current_price": 180.0,
            "market_value": 18000.0,
            "unrealized_gain_loss": 3000.0,
            "asset_class": "Equity",
            "purchase_date": "2020-01-15",
        },
    ]

    portfolio = build_portfolio(holdings_with_securities, [], [], None)

    aapl_pos = next(p for p in portfolio.positions if p.ticker == "AAPL")
    assert aapl_pos.inception_date == date(2020, 1, 15)


def test_build_portfolio_empty_positions():
    """Empty positions list should not cause errors in portfolio_pct calculation."""
    portfolio = build_portfolio([], [], [], None)

    assert len(portfolio.positions) == 0
    assert len(portfolio.holdings) == 0


def test_build_portfolio_grouping_logic():
    """Positions should be correctly grouped by asset class for hierarchical display."""
    holdings_with_securities = [
        {
            "ticker": "VTI",
            "security_name": "Vanguard Total Stock Market",
            "quantity": 100,
            "cost_basis": 18000,
            "current_price": 200.0,
            "market_value": 20000.0,
            "unrealized_gain_loss": 2000.0,
            "asset_class": "US Equities",
        },
        {
            "ticker": "VXUS",
            "security_name": "Vanguard Total International Stock",
            "quantity": 50,
            "cost_basis": 3000,
            "current_price": 65.0,
            "market_value": 3250.0,
            "unrealized_gain_loss": 250.0,
            "asset_class": "US Equities",
        },
        {
            "ticker": "BND",
            "security_name": "Vanguard Total Bond Market",
            "quantity": 100,
            "cost_basis": 8000,
            "current_price": 82.0,
            "market_value": 8200.0,
            "unrealized_gain_loss": 200.0,
            "asset_class": "Fixed Income",
        },
    ]

    portfolio = build_portfolio(holdings_with_securities, [], [], None)

    # Check that positions have correct portfolio percentages
    vti_pos = next(p for p in portfolio.positions if p.ticker == "VTI")
    vxus_pos = next(p for p in portfolio.positions if p.ticker == "VXUS")
    bnd_pos = next(p for p in portfolio.positions if p.ticker == "BND")

    assert vti_pos.portfolio_pct == pytest.approx(20000.0 / 31450.0)
    assert vxus_pos.portfolio_pct == pytest.approx(3250.0 / 31450.0)
    assert bnd_pos.portfolio_pct == pytest.approx(8200.0 / 31450.0)

    # Check that all portfolio percentages sum to 1
    total_pct = vti_pos.portfolio_pct + vxus_pos.portfolio_pct + bnd_pos.portfolio_pct
    assert total_pct == pytest.approx(1.0)


def test_projected_cash_flows_inflow_source_keys_are_lowercase():
    """inflow_sources keys must be lowercase to match generator.py lookups."""
    from wealth_management_portal_report.models import Holding
    from wealth_management_portal_report.transformers import _build_projected_cash_flows

    holdings = [Holding(asset="Equity", allocation=1.0, value=100_000.0)]
    ie = {
        "client_id": "c1",
        "as_of_date": "2024-01-01",
        "monthly_income": 5000,
        "monthly_expenses": 4000,
        "sustainability_years": 20,
    }
    result = _build_projected_cash_flows(holdings, ie)
    keys = result[0].inflow_sources.keys()
    assert "dividends" in keys
    assert "income" in keys
    assert "Dividends" not in keys


def test_aggregate_performance_volatility():
    """Volatility is annualised std dev of quarterly TWRs."""
    records = [
        {
            "performance_id": "p1",
            "portfolio_id": "port1",
            "period": "2024-Q1",
            "period_start_date": "2024-01-01",
            "period_end_date": "2024-03-31",
            "time_weighted_return": 0.04,
        },
        {
            "performance_id": "p2",
            "portfolio_id": "port1",
            "period": "2024-Q2",
            "period_start_date": "2024-04-01",
            "period_end_date": "2024-06-30",
            "time_weighted_return": 0.02,
        },
        {
            "performance_id": "p3",
            "portfolio_id": "port1",
            "period": "2024-Q3",
            "period_start_date": "2024-07-01",
            "period_end_date": "2024-09-30",
            "time_weighted_return": 0.06,
        },
    ]
    perf = _aggregate_performance(records)
    assert perf.volatility is not None
    assert perf.volatility > 0


def test_aggregate_performance_max_drawdown():
    """Max drawdown is computed from cumulative return series."""
    records = [
        {
            "performance_id": "p1",
            "portfolio_id": "port1",
            "period": "2024-Q1",
            "period_start_date": "2024-01-01",
            "period_end_date": "2024-03-31",
            "time_weighted_return": 0.10,  # peak at 1.10
        },
        {
            "performance_id": "p2",
            "portfolio_id": "port1",
            "period": "2024-Q2",
            "period_start_date": "2024-04-01",
            "period_end_date": "2024-06-30",
            "time_weighted_return": -0.20,  # drops to 0.88 -> drawdown ~20%
        },
    ]
    perf = _aggregate_performance(records)
    assert perf.max_drawdown is not None
    # drawdown = (1.10 - 0.88) / 1.10 ~= 0.2
    assert perf.max_drawdown == pytest.approx(0.2, abs=0.01)


def test_aggregate_performance_single_record_no_risk_metrics():
    """Single record: volatility and max_drawdown are None (need >=2 records)."""
    records = [
        {
            "performance_id": "p1",
            "portfolio_id": "port1",
            "period": "2024-Q1",
            "period_start_date": "2024-01-01",
            "period_end_date": "2024-03-31",
            "time_weighted_return": 0.05,
        },
    ]
    perf = _aggregate_performance(records)
    assert perf.volatility is None
    assert perf.max_drawdown is None


def test_aggregate_performance_zero_drawdown_returns_zero_not_none():
    """All-positive returns: max_drawdown is 0.0, not None."""
    records = [
        {
            "performance_id": "p1",
            "portfolio_id": "port1",
            "period": "2024-Q1",
            "period_start_date": "2024-01-01",
            "period_end_date": "2024-03-31",
            "time_weighted_return": 0.05,
        },
        {
            "performance_id": "p2",
            "portfolio_id": "port1",
            "period": "2024-Q2",
            "period_start_date": "2024-04-01",
            "period_end_date": "2024-06-30",
            "time_weighted_return": 0.03,
        },
    ]
    perf = _aggregate_performance(records)
    assert perf.max_drawdown == 0.0
    assert perf.max_drawdown is not None


def test_normalise_asset_class_synonyms():
    """Test asset class synonym normalisation."""
    from wealth_management_portal_report.transformers import _normalise_asset_class

    assert _normalise_asset_class("Stocks") == "Equity"
    assert _normalise_asset_class("Bonds") == "Fixed Income"
    assert _normalise_asset_class("Bond") == "Fixed Income"
    assert _normalise_asset_class("Equities") == "Equity"
    assert _normalise_asset_class("Stock") == "Equity"


def test_normalise_asset_class_no_synonym():
    """Test asset class normalisation when no synonym exists."""
    from wealth_management_portal_report.transformers import _normalise_asset_class

    assert _normalise_asset_class("Cash") == "Cash"
    assert _normalise_asset_class("Alternatives") == "Alternatives"
    assert _normalise_asset_class("Real Estate") == "Real Estate"


def test_parse_target_allocation_normalises_synonyms():
    """Test target allocation parsing normalises asset class synonyms."""
    result = _parse_target_allocation("85% Stocks, 10% Bonds, 5% Cash")

    assert len(result) == 3
    stocks = next(r for r in result if r.asset == "Equity")
    bonds = next(r for r in result if r.asset == "Fixed Income")
    cash = next(r for r in result if r.asset == "Cash")

    assert stocks.target == pytest.approx(0.85)
    assert bonds.target == pytest.approx(0.10)
    assert cash.target == pytest.approx(0.05)


def test_build_portfolio_normalises_holding_asset_classes():
    """Test portfolio building normalises holding asset classes to match targets."""
    holdings_with_securities = [
        {
            "ticker": "AAPL",
            "security_name": "Apple Inc",
            "quantity": 100,
            "market_value": 100000.0,
            "asset_class": "Stocks",  # Should be normalised to "Equity"
        },
        {
            "ticker": "BND",
            "security_name": "Vanguard Total Bond Market",
            "quantity": 1000,
            "market_value": 50000.0,
            "asset_class": "Bonds",  # Should be normalised to "Fixed Income"
        },
    ]

    portfolio = build_portfolio(holdings_with_securities, [], [], None)

    # Check positions have normalised asset classes
    aapl_pos = next(p for p in portfolio.positions if p.ticker == "AAPL")
    bnd_pos = next(p for p in portfolio.positions if p.ticker == "BND")

    assert aapl_pos.asset_class == "Equity"
    assert bnd_pos.asset_class == "Fixed Income"

    # Check holdings aggregation uses normalised names
    equity_holding = next(h for h in portfolio.holdings if h.asset == "Equity")
    bond_holding = next(h for h in portfolio.holdings if h.asset == "Fixed Income")

    assert equity_holding.value == 100000.0
    assert bond_holding.value == 50000.0


def test_build_portfolio_logs_warning_for_unmatched_asset_class(caplog):
    """Test portfolio building logs warning for asset classes with no matching target."""
    import logging

    holdings_with_securities = [
        {
            "ticker": "GOLD",
            "security_name": "Gold ETF",
            "quantity": 100,
            "market_value": 50000.0,
            "asset_class": "Commodities",  # No target allocation for this
        },
    ]

    portfolio_record = {"target_allocation": "70% Equity, 30% Fixed Income"}

    with caplog.at_level(logging.WARNING):
        build_portfolio(holdings_with_securities, [], [], None, portfolio_record)

    # Should log warning for unmatched asset class
    assert "No target allocation found for asset class: Commodities" in caplog.text


def test_build_projected_portfolio_values_basic():
    """Test basic projected portfolio values calculation."""
    from wealth_management_portal_report.models import PerformanceMetrics, ProjectedCashFlow
    from wealth_management_portal_report.transformers import _build_projected_portfolio_values

    # Portfolio starting value: $100k
    positions = [
        {"market_value": 60000.0, "volatility": 0.12},  # 60k with 12% volatility
        {"market_value": 40000.0, "volatility": 0.08},  # 40k with 8% volatility
    ]

    performance = PerformanceMetrics(ytd=0.08, one_year=0.08, since_inception=0.10)

    projected_cash_flows = [
        ProjectedCashFlow(period="2024-Q4", known_inflows=1000, estimated_outflows=2000, inflow_sources={}),
        ProjectedCashFlow(period="2025-Q1", known_inflows=1000, estimated_outflows=2000, inflow_sources={}),
        ProjectedCashFlow(period="2025-Q2", known_inflows=1000, estimated_outflows=2000, inflow_sources={}),
        ProjectedCashFlow(period="2025-Q3", known_inflows=1000, estimated_outflows=2000, inflow_sources={}),
    ]

    result = _build_projected_portfolio_values(positions, performance, projected_cash_flows)

    assert len(result) == 4
    assert all(pv.period.startswith("20") for pv in result)

    # Check that conservative < base < optimistic for each period
    for pv in result:
        assert pv.conservative < pv.base < pv.optimistic


def test_build_projected_portfolio_values_no_volatility():
    """Test projected values when positions have no volatility data."""
    from wealth_management_portal_report.models import PerformanceMetrics
    from wealth_management_portal_report.transformers import _build_projected_portfolio_values

    positions = [{"market_value": 100000.0, "volatility": None}]
    performance = PerformanceMetrics(ytd=0.08, one_year=0.08, since_inception=0.10)

    result = _build_projected_portfolio_values(positions, performance, [])

    # When no volatility, conservative = base = optimistic
    for pv in result:
        assert pv.conservative == pv.base == pv.optimistic


def test_build_projected_portfolio_values_no_cash_flows():
    """Test projected values with no projected cash flows."""
    from wealth_management_portal_report.models import PerformanceMetrics
    from wealth_management_portal_report.transformers import _build_projected_portfolio_values

    positions = [{"market_value": 100000.0, "volatility": 0.10}]
    performance = PerformanceMetrics(ytd=0.08, one_year=0.08, since_inception=0.10)

    result = _build_projected_portfolio_values(positions, performance, [])

    assert len(result) == 4
    # Values should grow each quarter without cash flows
    assert result[1].base > result[0].base


def test_build_projected_portfolio_values_uses_since_inception_fallback():
    """Test that since_inception is used when one_year is not available."""
    from wealth_management_portal_report.models import PerformanceMetrics
    from wealth_management_portal_report.transformers import _build_projected_portfolio_values

    positions = [{"market_value": 100000.0, "volatility": 0.10}]
    performance = PerformanceMetrics(ytd=0.05, one_year=0.0, since_inception=0.12)

    result = _build_projected_portfolio_values(positions, performance, [])

    # Should use since_inception (12%) annualized / 4 = 3% quarterly
    # Starting value 100k, after 1 quarter: ~103k
    assert result[0].base > 102000
    assert result[0].base < 104000
