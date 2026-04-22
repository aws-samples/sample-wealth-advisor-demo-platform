# Integration tests for all repositories against real Redshift
# Requires IAM credentials and a reachable Redshift Serverless workgroup.
import uuid
from datetime import UTC, date, datetime

import pytest

from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory
from wealth_management_portal_portfolio_data_access.models.account import Account
from wealth_management_portal_portfolio_data_access.models.client import Client, ClientRestriction
from wealth_management_portal_portfolio_data_access.models.income_expense import ClientIncomeExpense
from wealth_management_portal_portfolio_data_access.models.interaction import Interaction
from wealth_management_portal_portfolio_data_access.models.market import Article, Theme, ThemeArticleAssociation
from wealth_management_portal_portfolio_data_access.models.performance import PerformanceRecord
from wealth_management_portal_portfolio_data_access.models.portfolio import Holding, PortfolioRecord, Security
from wealth_management_portal_portfolio_data_access.models.recommended_product import RecommendedProduct
from wealth_management_portal_portfolio_data_access.models.report_record import ClientReport
from wealth_management_portal_portfolio_data_access.repositories import (
    InteractionRepository,
    PerformanceRepository,
    PortfolioRepository,
    ReportRepository,
    create_simple_repos,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def conn_factory():
    """Shared IAM connection factory for all integration tests."""
    return iam_connection_factory()


@pytest.fixture(scope="module")
def repos(conn_factory):
    """All simple repositories backed by real Redshift."""
    return create_simple_repos(conn_factory)


# --- Simple repositories ---


def test_clients_schema(repos):
    """Clients table is queryable and rows parse into Client model."""
    results = repos["client"].get()
    assert isinstance(results, list)
    if results:
        assert isinstance(results[0], Client)


def test_client_get_one(repos):
    """get_one returns a single Client or None."""
    clients = repos["client"].get()
    if not clients:
        pytest.skip("No clients in DB")
    result = repos["client"].get_one(client_id=clients[0].client_id)
    assert isinstance(result, Client)
    assert result.client_id == clients[0].client_id


def test_restrictions_schema(repos):
    """Client investment restrictions table is queryable."""
    results = repos["restriction"].get()
    assert isinstance(results, list)
    if results:
        assert isinstance(results[0], ClientRestriction)


def test_accounts_schema(repos):
    """Accounts table is queryable and rows parse into Account model."""
    results = repos["account"].get()
    assert isinstance(results, list)
    if results:
        assert isinstance(results[0], Account)


def test_portfolios_schema(repos):
    """Portfolios table is queryable and rows parse into PortfolioRecord model."""
    results = repos["portfolio"].get()
    assert isinstance(results, list)
    if results:
        assert isinstance(results[0], PortfolioRecord)


def test_holdings_schema(repos):
    """Holdings table is queryable and rows parse into Holding model."""
    results = repos["holding"].get()
    assert isinstance(results, list)
    if results:
        assert isinstance(results[0], Holding)


def test_securities_schema(repos):
    """Securities table is queryable and rows parse into Security model."""
    results = repos["security"].get()
    assert isinstance(results, list)
    if results:
        assert isinstance(results[0], Security)


def test_themes_schema(repos):
    """Themes table is queryable and rows parse into Theme model."""
    results = repos["theme"].get()
    assert len(results) > 0
    theme = results[0]
    assert isinstance(theme, Theme)
    assert theme.theme_id  # non-empty string
    assert theme.sentiment in ("bullish", "bearish", "neutral", None)
    assert theme.title  # non-empty string


def test_theme_article_associations_schema(repos):
    """Theme article associations table is queryable and rows parse into ThemeArticleAssociation model."""
    results = repos["theme_article_association"].get()
    assert len(results) > 0
    association = results[0]
    assert isinstance(association, ThemeArticleAssociation)
    assert association.theme_id  # non-empty string
    assert association.article_hash  # non-empty string


def test_articles_schema(repos):
    """Articles table is queryable and rows parse into Article model."""
    results = repos["article"].get()
    assert len(results) > 0
    article = results[0]
    assert isinstance(article, Article)
    assert article.content_hash  # non-empty string
    # published_date parses without error (already validated by Pydantic on load)
    if article.published_date is not None:
        assert isinstance(article.published_date, datetime)


def test_income_expense_schema(repos):
    """Client income/expense table is queryable and rows parse into ClientIncomeExpense model."""
    results = repos["income_expense"].get()
    assert isinstance(results, list)
    if results:
        assert isinstance(results[0], ClientIncomeExpense)


def test_recommended_products_schema(repos):
    """Recommended products table is queryable and rows parse into RecommendedProduct model."""
    results = repos["recommended_product"].get()
    assert isinstance(results, list)
    assert len(results) > 0  # seeded data expected
    assert isinstance(results[0], RecommendedProduct)


# --- PortfolioRepository ---


def test_get_holdings_with_securities(conn_factory, repos):
    """JOIN query returns holdings enriched with security fields."""
    portfolios = repos["portfolio"].get()
    if not portfolios:
        pytest.skip("No portfolios in DB")
    repo = PortfolioRepository(conn_factory)
    results = repo.get_holdings_with_securities(portfolios[0].portfolio_id)
    assert isinstance(results, list)
    if results:
        assert "ticker" in results[0]
        assert "security_name" in results[0]
        assert "asset_class" in results[0]


# --- PerformanceRepository ---


def test_performance_get_for_period(conn_factory, repos):
    """Date-range query returns PerformanceRecord list."""
    portfolios = repos["portfolio"].get()
    if not portfolios:
        pytest.skip("No portfolios in DB")
    repo = PerformanceRepository(conn_factory)
    results = repo.get_for_period(
        portfolios[0].portfolio_id,
        date(2000, 1, 1),
        date(2030, 12, 31),
    )
    assert isinstance(results, list)
    if results:
        assert isinstance(results[0], PerformanceRecord)
        # Verify ordering
        dates = [r.period_start_date for r in results]
        assert dates == sorted(dates)


# --- InteractionRepository ---


def test_interaction_get_recent(conn_factory, repos):
    """Ordered/limited query returns Interaction list."""
    clients = repos["client"].get()
    if not clients:
        pytest.skip("No clients in DB")
    repo = InteractionRepository(conn_factory)
    results = repo.get_recent(clients[0].client_id, limit=5)
    assert isinstance(results, list)
    assert len(results) <= 5
    if results:
        assert isinstance(results[0], Interaction)
        # Verify descending order
        dates = [r.interaction_date for r in results]
        assert dates == sorted(dates, reverse=True)


# --- ReportRepository (write operations) ---


@pytest.fixture
def test_report(conn_factory):
    """Insert a test report record and clean it up after the test."""
    report = ClientReport(
        report_id=f"RPT-{uuid.uuid4().hex[:10].upper()}",
        client_id="CLT-001",
        s3_path="s3://test-bucket/test-report.pdf",
        generated_date=datetime.now(UTC),
    )
    repo = ReportRepository(conn_factory)
    repo.save(report)
    yield report
    # Cleanup
    with conn_factory() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.client_reports WHERE report_id = %s", [report.report_id])
        conn.commit()


def test_report_save(conn_factory, test_report):
    """Saved report is retrievable from Redshift."""
    repo = ReportRepository(conn_factory)
    result = repo.get_one(report_id=test_report.report_id)
    assert result is not None
    assert result.report_id == test_report.report_id
    assert result.s3_path == test_report.s3_path


def test_report_update_download_date(conn_factory, test_report):
    """update_download_date persists the timestamp to Redshift."""
    repo = ReportRepository(conn_factory)
    download_time = datetime.now(UTC)
    repo.update_download_date(test_report.report_id, download_time)
    result = repo.get_one(report_id=test_report.report_id)
    assert result is not None
    assert result.download_date is not None


def test_report_update_status(conn_factory, test_report):
    """update_status persists status and s3_path changes to Redshift."""
    repo = ReportRepository(conn_factory)
    new_s3_path = "reports/CLT-001/updated-report.pdf"
    repo.update_status(test_report.report_id, "complete", new_s3_path)
    result = repo.get_one(report_id=test_report.report_id)
    assert result is not None
    assert result.status == "complete"
    assert result.s3_path == new_s3_path


def test_report_update_status_with_s3_path(conn_factory, test_report):
    """update_status can update both status and s3_path."""
    repo = ReportRepository(conn_factory)
    new_s3_path = "reports/CLT-001/RPT-A1B2C3D4E5.pdf"
    repo.update_status(test_report.report_id, "complete", new_s3_path)
    result = repo.get_one(report_id=test_report.report_id)
    assert result is not None
    assert result.status == "complete"
    assert result.s3_path == new_s3_path


def test_report_get_latest_by_client(conn_factory):
    """get_latest_by_client returns the most recent report for a client."""
    # Create two test reports for the same client
    client_id = "CLT-001"
    report1 = ClientReport(
        report_id=f"RPT-{uuid.uuid4().hex[:10].upper()}",
        client_id=client_id,
        s3_path="s3://test-bucket/report1.pdf",
        generated_date=datetime(2024, 1, 1, 12, 0),  # Remove timezone for compatibility
        status="complete",
    )
    report2 = ClientReport(
        report_id=f"RPT-{uuid.uuid4().hex[:10].upper()}",
        client_id=client_id,
        s3_path="s3://test-bucket/report2.pdf",
        generated_date=datetime(2024, 1, 2, 12, 0),  # Remove timezone for compatibility
        status="complete",
    )

    repo = ReportRepository(conn_factory)
    repo.save(report1)
    repo.save(report2)

    try:
        result = repo.get_latest_by_client(client_id)
        assert result is not None
        assert result.report_id == report2.report_id  # More recent one
        assert result.generated_date == report2.generated_date
    finally:
        # Cleanup
        with conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.client_reports WHERE report_id IN (%s, %s)",
                    [report1.report_id, report2.report_id],
                )
            conn.commit()


def test_report_get_latest_by_client_none(conn_factory):
    """get_latest_by_client returns None when no reports exist for client."""
    repo = ReportRepository(conn_factory)
    result = repo.get_latest_by_client("NONEXISTENT")
    assert result is None
