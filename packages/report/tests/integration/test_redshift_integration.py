import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env from the repo root
load_dotenv(Path(__file__).resolve().parents[4] / ".env")

from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory  # noqa: E402
from wealth_management_portal_portfolio_data_access.repositories import (  # noqa: E402
    PortfolioRepository,
    create_simple_repos,
)

# Skip entire module if Redshift not available and mark as integration tests
pytestmark = [
    pytest.mark.skipif(not os.environ.get("REDSHIFT_DATABASE"), reason="Redshift not available"),
    pytest.mark.integration,
]


@pytest.fixture(scope="module")
def conn_factory():
    """Create Redshift connection factory for tests."""
    return iam_connection_factory()


@pytest.fixture(scope="module")
def repos(conn_factory):
    """Create repository instances."""
    return {
        **create_simple_repos(conn_factory),
        "portfolio_repo": PortfolioRepository(conn_factory),
    }


@pytest.fixture(scope="module")
def client_with_accounts(repos):
    """Find a client that has at least one account — needed for data-dependent tests."""
    clients = repos["client"].get()
    for c in clients:
        if repos["account"].get(client_id=c.client_id):
            return c
    pytest.skip("No client with accounts found in DB")


def test_load_client_from_redshift(repos):
    """Query client via BaseRepository, verify Client model fields populated."""
    clients = repos["client"].get()
    if not clients:
        pytest.skip("No clients in DB")
    client = clients[0]
    assert client.client_id
    assert client.client_first_name
    assert client.client_last_name


def test_load_accounts_for_client(repos, client_with_accounts):
    """Query accounts for a client, verify list is non-empty and fields populated."""
    accounts = repos["account"].get(client_id=client_with_accounts.client_id)
    assert len(accounts) > 0
    for account in accounts:
        assert account.account_type
        assert account.current_balance is not None


def test_load_restrictions_for_client(repos):
    """Query restrictions for a client, verify restriction text populated."""
    clients = repos["client"].get()
    if not clients:
        pytest.skip("No clients in DB")
    restrictions = repos["restriction"].get(client_id=clients[0].client_id)
    assert isinstance(restrictions, list)
    # Not all clients have restrictions — just verify the query works


def test_portfolio_holdings_with_securities(repos):
    """Use PortfolioRepository join, verify enriched dicts have ticker + asset_class."""
    accounts = repos["account"].get()
    if not accounts:
        pytest.skip("No accounts in DB")
    portfolios = repos["portfolio"].get(account_id=accounts[0].account_id)
    if not portfolios:
        pytest.skip("No portfolios for account")
    holdings = repos["portfolio_repo"].get_holdings_with_securities(portfolios[0].portfolio_id)
    assert len(holdings) > 0
    for holding in holdings:
        assert "ticker" in holding
        assert "asset_class" in holding


def test_full_pipeline_client_to_report(repos, client_with_accounts, conn_factory):
    """Load all data from Redshift, transform via builders, verify report models are populated."""
    from datetime import date

    from wealth_management_portal_portfolio_data_access.repositories import (
        InteractionRepository,
        PerformanceRepository,
        PortfolioRepository,
    )

    from wealth_management_portal_report.transformers import (
        build_client_profile,
        build_communications,
        build_portfolio,
    )

    client = client_with_accounts

    accounts = repos["account"].get(client_id=client.client_id)
    restrictions = repos["restriction"].get(client_id=client.client_id)
    portfolios = repos["portfolio"].get(account_id=accounts[0].account_id) if accounts else []

    portfolio_repo = PortfolioRepository(conn_factory)
    holdings = portfolio_repo.get_holdings_with_securities(portfolios[0].portfolio_id) if portfolios else []

    perf_repo = PerformanceRepository(conn_factory)
    performance = (
        perf_repo.get_for_period(portfolios[0].portfolio_id, date(2000, 1, 1), date(2030, 12, 31)) if portfolios else []
    )

    transactions = repos["transaction"].get(account_id=accounts[0].account_id) if accounts else []

    interaction_repo = InteractionRepository(conn_factory)
    interactions = interaction_repo.get_recent(client.client_id, limit=10)

    income_expense = repos["income_expense"].get(client_id=client.client_id)
    income_expense_record = income_expense[0] if income_expense else None

    profile = build_client_profile(client, restrictions, accounts, transactions)
    portfolio_model = build_portfolio(holdings, performance, transactions, income_expense_record)
    communications = build_communications(interactions)

    assert profile.names
    assert profile.aum >= 0
    assert isinstance(portfolio_model.holdings, list)
    assert isinstance(communications.meetings, list)
