# Repository unit tests using a mock PEP 249 connection — no real DB required
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from wealth_management_portal_portfolio_data_access.models.client import Client
from wealth_management_portal_portfolio_data_access.models.report_record import ClientReport
from wealth_management_portal_portfolio_data_access.repositories import (
    BaseRepository,
    ClientReportRepository,
    InteractionRepository,
    PerformanceRepository,
    PortfolioRepository,
    ReportRepository,
)


def make_conn_factory(columns: list[str], rows: list[tuple]):
    """Build a mock PEP 249 conn_factory returning the given columns and rows."""
    cursor = MagicMock()
    cursor.description = [(col,) for col in columns]
    cursor.fetchall.return_value = rows
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)

    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = lambda s: s
    conn.__exit__ = MagicMock(return_value=False)

    def conn_factory():
        return conn

    return conn_factory, cursor


# --- BaseRepository ---


def test_base_get_no_filters():
    cols = [
        "client_id",
        "client_first_name",
        "client_last_name",
        "email",
        "phone",
        "address",
        "city",
        "state",
        "zip",
        "date_of_birth",
        "risk_tolerance",
        "investment_objectives",
        "segment",
        "status",
        "advisor_id",
        "client_since",
        "service_model",
        "sophistication",
        "qualified_investor",
    ]
    row = (
        "C1",
        "Alice",
        "Smith",
        "alice@example.com",
        None,
        None,
        None,
        None,
        None,
        date(1980, 1, 1),
        "Moderate",
        None,
        "HNW",
        "Active",
        "A1",
        date(2020, 1, 1),
        None,
        None,
        False,
    )
    conn_factory, cursor = make_conn_factory(cols, [row])
    repo = BaseRepository(conn_factory, Client, "public.client_search", set(cols))
    results = repo.get()
    assert len(results) == 1
    assert results[0].client_id == "C1"
    cursor.execute.assert_called_once_with("SELECT * FROM public.client_search", [])


def test_base_get_with_filter():
    cols = [
        "client_id",
        "client_first_name",
        "client_last_name",
        "email",
        "phone",
        "address",
        "city",
        "state",
        "zip",
        "date_of_birth",
        "risk_tolerance",
        "investment_objectives",
        "segment",
        "status",
        "advisor_id",
        "client_since",
        "service_model",
        "sophistication",
        "qualified_investor",
    ]
    row = (
        "C1",
        "Alice",
        "Smith",
        "alice@example.com",
        None,
        None,
        None,
        None,
        None,
        date(1980, 1, 1),
        "Moderate",
        None,
        "HNW",
        "Active",
        "A1",
        date(2020, 1, 1),
        None,
        None,
        False,
    )
    conn_factory, cursor = make_conn_factory(cols, [row])
    repo = BaseRepository(conn_factory, Client, "public.client_search", set(cols))
    results = repo.get(client_id="C1")
    assert results[0].client_id == "C1"
    cursor.execute.assert_called_once_with("SELECT * FROM public.client_search WHERE client_id = %s", ["C1"])


def test_base_get_one_returns_first():
    cols = [
        "client_id",
        "client_first_name",
        "client_last_name",
        "email",
        "phone",
        "address",
        "city",
        "state",
        "zip",
        "date_of_birth",
        "risk_tolerance",
        "investment_objectives",
        "segment",
        "status",
        "advisor_id",
        "client_since",
        "service_model",
        "sophistication",
        "qualified_investor",
    ]
    row = (
        "C1",
        "Alice",
        "Smith",
        "alice@example.com",
        None,
        None,
        None,
        None,
        None,
        date(1980, 1, 1),
        "Moderate",
        None,
        "HNW",
        "Active",
        "A1",
        date(2020, 1, 1),
        None,
        None,
        False,
    )
    conn_factory, _ = make_conn_factory(cols, [row])
    repo = BaseRepository(conn_factory, Client, "public.client_search", set(cols))
    result = repo.get_one(client_id="C1")
    assert result is not None
    assert result.client_id == "C1"


def test_base_get_one_returns_none_when_empty():
    cols = [
        "client_id",
        "client_first_name",
        "client_last_name",
        "email",
        "phone",
        "address",
        "city",
        "state",
        "zip",
        "date_of_birth",
        "risk_tolerance",
        "investment_objectives",
        "segment",
        "status",
        "advisor_id",
        "client_since",
        "service_model",
        "sophistication",
        "qualified_investor",
    ]
    conn_factory, _ = make_conn_factory(cols, [])
    repo = BaseRepository(conn_factory, Client, "public.client_search", set(cols))
    assert repo.get_one(client_id="MISSING") is None


def test_base_get_rejects_unknown_column():
    conn_factory, _ = make_conn_factory(["client_id"], [])
    repo = BaseRepository(conn_factory, Client, "public.client_search", {"client_id"})
    with pytest.raises(ValueError, match="Unknown column"):
        repo.get(nonexistent_col="x")


# --- PortfolioRepository ---


def test_portfolio_get_holdings_with_securities():
    cols = [
        "position_id",
        "portfolio_id",
        "security_id",
        "quantity",
        "cost_basis",
        "current_price",
        "market_value",
        "unrealized_gain_loss",
        "as_of_date",
        "ticker",
        "security_name",
        "asset_class",
        "sector",
    ]
    row = (
        "POS1",
        "PORT1",
        "SEC1",
        Decimal("10"),
        Decimal("100"),
        Decimal("110"),
        Decimal("1100"),
        Decimal("100"),
        date(2024, 1, 1),
        "AAPL",
        "Apple Inc",
        "Equity",
        "Technology",
    )
    conn_factory, cursor = make_conn_factory(cols, [row])
    repo = PortfolioRepository(conn_factory)
    results = repo.get_holdings_with_securities("PORT1")
    assert len(results) == 1
    assert results[0]["ticker"] == "AAPL"
    assert "PORT1" in cursor.execute.call_args[0][1]


# --- PerformanceRepository ---


def test_performance_get_for_period():
    cols = [
        "performance_id",
        "portfolio_id",
        "period",
        "period_start_date",
        "period_end_date",
        "time_weighted_return",
        "benchmark_return",
        "beginning_value",
        "ending_value",
    ]
    row = (
        "PERF1",
        "PORT1",
        "Q1",
        date(2024, 1, 1),
        date(2024, 3, 31),
        Decimal("0.05"),
        Decimal("0.04"),
        Decimal("100000"),
        Decimal("105000"),
    )
    conn_factory, cursor = make_conn_factory(cols, [row])
    repo = PerformanceRepository(conn_factory)
    results = repo.get_for_period("PORT1", date(2024, 1, 1), date(2024, 3, 31))
    assert len(results) == 1
    assert results[0].performance_id == "PERF1"
    args = cursor.execute.call_args[0][1]
    assert args[0] == "PORT1"


# --- InteractionRepository ---


def test_interaction_get_recent():
    cols = [
        "interaction_id",
        "client_id",
        "advisor_id",
        "interaction_type",
        "interaction_date",
        "subject",
        "summary",
        "sentiment",
        "duration_minutes",
    ]
    row = ("INT1", "C1", "ADV1", "Call", date(2024, 1, 10), "Review", "Discussed portfolio", "Positive", 30)
    conn_factory, cursor = make_conn_factory(cols, [row])
    repo = InteractionRepository(conn_factory)
    results = repo.get_recent("C1", limit=5)
    assert len(results) == 1
    assert results[0].interaction_id == "INT1"
    args = cursor.execute.call_args[0][1]
    assert args == ["C1", 5]


# --- ReportRepository ---


def test_report_save():
    conn_factory, cursor = make_conn_factory(
        ["report_id", "client_id", "s3_path", "generated_date", "download_date"], []
    )
    repo = ReportRepository(conn_factory)
    report = ClientReport(
        report_id="R1",
        client_id="C1",
        s3_path="s3://bucket/r1.pdf",
        generated_date=datetime(2024, 1, 1, 12, 0),
        download_date=None,
        next_best_action="Schedule a portfolio review call",
    )
    repo.save(report)
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    params = cursor.execute.call_args[0][1]
    assert "INSERT INTO public.client_reports" in sql
    assert "next_best_action" in sql
    assert "Schedule a portfolio review call" in params


def test_report_update_download_date():
    conn_factory, cursor = make_conn_factory(
        ["report_id", "client_id", "s3_path", "generated_date", "download_date"], []
    )
    repo = ReportRepository(conn_factory)
    dl = datetime(2024, 2, 1, 9, 0)
    repo.update_download_date("R1", dl)
    cursor.execute.assert_called_once()
    args = cursor.execute.call_args[0][1]
    assert args == [dl, "R1"]


def test_report_update_status_only():
    conn_factory, cursor = make_conn_factory(
        ["report_id", "client_id", "s3_path", "generated_date", "download_date", "status"], []
    )
    repo = ReportRepository(conn_factory)
    repo.update_status("R1", "complete")
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    args = cursor.execute.call_args[0][1]
    assert "UPDATE public.client_reports SET status = %s WHERE report_id = %s" in sql
    assert args == ["complete", "R1"]


def test_report_update_status_with_s3_path():
    conn_factory, cursor = make_conn_factory(
        ["report_id", "client_id", "s3_path", "generated_date", "download_date", "status"], []
    )
    repo = ReportRepository(conn_factory)
    repo.update_status("R1", "complete", "reports/CLT-001/RPT-A1B2C3D4E5.pdf")
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    args = cursor.execute.call_args[0][1]
    assert "UPDATE public.client_reports SET status = %s, s3_path = %s WHERE report_id = %s" in sql
    assert args == ["complete", "reports/CLT-001/RPT-A1B2C3D4E5.pdf", "R1"]


def test_report_get_latest_by_client():
    cols = ["report_id", "client_id", "s3_path", "generated_date", "download_date", "status"]
    row = ("R1", "C1", "reports/C1/R1.pdf", datetime(2024, 1, 1, 12, 0), None, "complete")
    conn_factory, cursor = make_conn_factory(cols, [row])
    repo = ReportRepository(conn_factory)
    result = repo.get_latest_by_client("C1")
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    args = cursor.execute.call_args[0][1]
    assert "ORDER BY generated_date DESC" in sql
    assert "LIMIT 1" in sql
    assert args == ["C1"]
    assert result is not None
    assert result.report_id == "R1"
    assert result.status == "complete"


def test_report_get_latest_by_client_none():
    conn_factory, cursor = make_conn_factory(
        ["report_id", "client_id", "s3_path", "generated_date", "download_date", "status"], []
    )
    repo = ReportRepository(conn_factory)
    result = repo.get_latest_by_client("MISSING")
    assert result is None


# --- ClientReportRepository ---


def test_client_report_get_portfolios():
    cols = [
        "portfolio_id",
        "account_id",
        "portfolio_name",
        "investment_model",
        "target_allocation",
        "benchmark",
        "inception_date",
    ]
    row = ("PORT1", "ACC1", "Growth", "Aggressive", "80/20", "S&P500", date(2023, 1, 1))
    conn_factory, cursor = make_conn_factory(cols, [row])
    repo = ClientReportRepository(conn_factory)
    results = repo.get_portfolios("CLT-001")
    assert len(results) == 1
    assert results[0].portfolio_id == "PORT1"
    assert results[0].portfolio_name == "Growth"
    sql = cursor.execute.call_args[0][0]
    args = cursor.execute.call_args[0][1]
    assert "client_portfolio_holdings" in sql
    assert args == ["CLT-001"]


def test_client_report_get_holdings_with_securities():
    cols = [
        "portfolio_id",
        "portfolio_name",
        "position_id",
        "security_id",
        "quantity",
        "cost_basis",
        "current_price",
        "market_value",
        "unrealized_gain_loss",
        "as_of_date",
        "ticker",
        "security_name",
        "asset_class",
        "sector",
    ]
    row = (
        "PORT1",
        "Growth",
        "POS1",
        "SEC1",
        Decimal("10"),
        Decimal("100"),
        Decimal("110"),
        Decimal("1100"),
        Decimal("100"),
        date(2024, 1, 1),
        "AAPL",
        "Apple Inc",
        "Equity",
        "Technology",
    )
    conn_factory, cursor = make_conn_factory(cols, [row])
    repo = ClientReportRepository(conn_factory)
    results = repo.get_holdings_with_securities("CLT-001")
    assert len(results) == 1
    assert results[0]["ticker"] == "AAPL"
    sql = cursor.execute.call_args[0][0]
    args = cursor.execute.call_args[0][1]
    assert "client_portfolio_holdings" in sql
    assert args == ["CLT-001"]


def test_client_report_get_performance():
    cols = [
        "performance_id",
        "portfolio_id",
        "period",
        "period_start_date",
        "period_end_date",
        "time_weighted_return",
        "benchmark_return",
        "beginning_value",
        "ending_value",
    ]
    row = (
        "PERF1",
        "PORT1",
        "Q1",
        date(2024, 1, 1),
        date(2024, 3, 31),
        Decimal("0.05"),
        Decimal("0.04"),
        Decimal("100000"),
        Decimal("105000"),
    )
    conn_factory, cursor = make_conn_factory(cols, [row])
    repo = ClientReportRepository(conn_factory)
    results = repo.get_performance("CLT-001")
    assert len(results) == 1
    assert results[0].performance_id == "PERF1"
    sql = cursor.execute.call_args[0][0]
    args = cursor.execute.call_args[0][1]
    assert "client_portfolio_performance" in sql
    assert args == ["CLT-001"]


def test_client_report_get_transactions():
    cols = [
        "transaction_id",
        "account_id",
        "security_id",
        "transaction_type",
        "transaction_date",
        "settlement_date",
        "quantity",
        "price",
        "amount",
        "status",
    ]
    row = (
        "TXN1",
        "ACC1",
        "SEC1",
        "BUY",
        date(2024, 1, 15),
        date(2024, 1, 17),
        Decimal("10"),
        Decimal("150"),
        Decimal("1500"),
        "Settled",
    )
    conn_factory, cursor = make_conn_factory(cols, [row])
    repo = ClientReportRepository(conn_factory)
    results = repo.get_transactions("CLT-001")
    assert len(results) == 1
    assert results[0].transaction_id == "TXN1"
    sql = cursor.execute.call_args[0][0]
    args = cursor.execute.call_args[0][1]
    assert "client_account_transactions" in sql
    assert args == ["CLT-001"]
