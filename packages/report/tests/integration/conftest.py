"""Fixtures that bypass MCP and call Redshift repositories directly."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def _load_env():
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env")


from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory  # noqa: E402
from wealth_management_portal_portfolio_data_access.repositories import (  # noqa: E402
    ClientReportRepository,
    InteractionRepository,
    ThemeRepository,
    create_simple_repos,
)

from wealth_management_portal_report.generator import ReportGenerator  # noqa: E402
from wealth_management_portal_report.report_agent.tools import ReportData  # noqa: E402
from wealth_management_portal_report.transformers import (  # noqa: E402
    build_client_profile,
    build_communications,
    build_market_context,
    build_portfolio,
)


@pytest.fixture(scope="module")
def _conn_factory():
    return iam_connection_factory()


@pytest.fixture(scope="module")
def _repos(_conn_factory):
    return create_simple_repos(_conn_factory)


@pytest.fixture(scope="module")
def _report_repo(_conn_factory):
    return ClientReportRepository(_conn_factory)


@pytest.fixture(scope="module")
def _interaction_repo(_conn_factory):
    return InteractionRepository(_conn_factory)


@pytest.fixture(scope="module")
def _theme_repo(_conn_factory):
    return ThemeRepository(_conn_factory)


def _serialize_value(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _serialize_dict(data):
    if isinstance(data, dict):
        return {k: _serialize_dict(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_serialize_dict(item) for item in data]
    return _serialize_value(data)


def _get_client_report_data(repos, report_repo, interaction_repo, theme_repo, client_id):
    """Replicate the Lambda gateway's _get_client_report_data using direct Redshift access."""
    client = repos["client"].get_one(client_id=client_id)
    if not client:
        return {"error": f"Client '{client_id}' not found. Use list_clients to see available clients."}

    restrictions = repos["restriction"].get(client_id=client.client_id)
    accounts = repos["account"].get(client_id=client.client_id)
    interactions = interaction_repo.get_recent(client.client_id, 50)
    income_expense_records = repos["income_expense"].get(client_id=client.client_id)
    recommended_products = repos["recommended_product"].get()
    themes = theme_repo.get(client_id=client_id)
    portfolios = report_repo.get_portfolios(client.client_id)
    holdings_with_securities = report_repo.get_holdings_with_securities(client.client_id)
    performance = report_repo.get_performance(client.client_id)
    transactions = report_repo.get_transactions(client.client_id)

    income_expense = income_expense_records[0] if income_expense_records else None

    return {
        "client": client.model_dump(mode="json"),
        "restrictions": [r.model_dump(mode="json") for r in restrictions],
        "accounts": [a.model_dump(mode="json") for a in accounts],
        "portfolios": [p.model_dump(mode="json") for p in portfolios],
        "holdings_with_securities": _serialize_dict(holdings_with_securities),
        "performance": [p.model_dump(mode="json") for p in performance],
        "transactions": [t.model_dump(mode="json") for t in transactions],
        "interactions": [i.model_dump(mode="json") for i in interactions],
        "income_expense": income_expense.model_dump(mode="json") if income_expense else None,
        "recommended_products": [rp.model_dump(mode="json") for rp in recommended_products],
        "themes": [t.model_dump(mode="json") for t in themes],
    }


def _direct_fetch_report_data(repos, report_repo, interaction_repo, theme_repo, client_id, **kwargs):
    """Replacement for fetch_report_data that bypasses MCP."""
    data = _get_client_report_data(repos, report_repo, interaction_repo, theme_repo, client_id)

    if "error" in data:
        raise RuntimeError(f"MCP get_client_report_data failed: {data['error']}")

    profile = build_client_profile(data["client"], data["restrictions"], data["accounts"], data["transactions"])
    portfolio_model = build_portfolio(
        data["holdings_with_securities"],
        data["performance"],
        data["transactions"],
        data.get("income_expense"),
        data["portfolios"][0] if data["portfolios"] else None,
    )
    communications = build_communications(data["interactions"])
    market_context = build_market_context(data["themes"], date.today())

    generator = ReportGenerator()
    components = generator.generate(
        profile, portfolio_model, communications, data["recommended_products"], market_context
    )

    return ReportData(
        components=components,
        profile=profile,
        portfolio=portfolio_model,
        communications=communications,
    )


@pytest.fixture(autouse=True)
def _patch_mcp(_repos, _report_repo, _interaction_repo, _theme_repo):
    """Patch fetch_report_data and save_report_via_mcp to bypass MCP for all integration tests."""

    def patched_fetch(client_id, mcp_client=None):
        return _direct_fetch_report_data(_repos, _report_repo, _interaction_repo, _theme_repo, client_id)

    def patched_save(report_id, client_id, s3_path, generated_date, status, next_best_action=None, mcp_client=None):
        pass  # no-op — don't write test data to Redshift

    # Patch in all modules where these are imported/used
    with (
        patch("wealth_management_portal_report.report_agent.tools.fetch_report_data", side_effect=patched_fetch),
        patch("wealth_management_portal_report.report_agent.tools.save_report_via_mcp", side_effect=patched_save),
        patch("wealth_management_portal_report.report_agent.main.fetch_report_data", side_effect=patched_fetch),
        patch("wealth_management_portal_report.report_agent.main.save_report_via_mcp", side_effect=patched_save),
        patch("wealth_management_portal_report.report_agent.main._get_mcp_client"),
    ):
        yield
