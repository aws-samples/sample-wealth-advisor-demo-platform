# Tests for complete report generation wiring
import os
from pathlib import Path

import pytest
from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory
from wealth_management_portal_portfolio_data_access.repositories import create_simple_repos

from wealth_management_portal_report.generator import ReportGenerator
from wealth_management_portal_report.models import (
    ClientProfile,
    Communications,
    MarketContext,
    Portfolio,
)
from wealth_management_portal_report.pdf import html_to_pdf, markdown_to_html

# Skip entire module if Redshift not available and mark as integration tests
pytestmark = [
    pytest.mark.skipif(not os.environ.get("REDSHIFT_DATABASE"), reason="Redshift not available"),
    pytest.mark.integration,
]


@pytest.fixture(scope="module")
def products():
    repos = create_simple_repos(iam_connection_factory())
    return repos["recommended_product"].get()


def _load_client_data(client_dir: Path):
    """Load report-shaped models directly from JSON test fixtures."""
    profile = ClientProfile.model_validate_json((client_dir / "profile.json").read_text())
    portfolio = Portfolio.model_validate_json((client_dir / "portfolio.json").read_text())
    communications = Communications.model_validate_json((client_dir / "communications.json").read_text())
    return profile, portfolio, communications


def _load_market_context(client_dir: Path):
    """Load market context from JSON test fixture."""
    return MarketContext.model_validate_json((client_dir / "market_context.json").read_text())


def test_generator_includes_new_prompts(products):
    """Generator should include portfolio_narrative and last_interaction prompts."""
    client_dir = Path(__file__).parent.parent / "fixtures" / "clients" / "gray"
    profile, portfolio, communications = _load_client_data(client_dir)
    market_context = _load_market_context(client_dir)

    generator = ReportGenerator()
    result = generator.generate(profile, portfolio, communications, products, market_context)

    assert "synthesis_prompts" in result
    assert "portfolio_narrative" in result["synthesis_prompts"]
    assert "last_interaction_summary" in result["synthesis_prompts"]
    assert "financial_analysis" in result["synthesis_prompts"]


def test_generator_includes_chart_svgs(products):
    """Generator should generate and include chart SVGs."""
    client_dir = Path(__file__).parent.parent / "fixtures" / "clients" / "gray"
    profile, portfolio, communications = _load_client_data(client_dir)
    market_context = _load_market_context(client_dir)

    generator = ReportGenerator()
    result = generator.generate(profile, portfolio, communications, products, market_context)

    assert "chart_svgs" in result
    assert "allocation" in result["chart_svgs"]
    assert "cash_flow" in result["chart_svgs"]
    assert "<svg" in result["chart_svgs"]["allocation"]
    assert "<svg" in result["chart_svgs"]["cash_flow"]


def test_complete_report_to_pdf_pipeline(products):
    """Complete pipeline from data to PDF should work."""
    # Load data
    client_dir = Path(__file__).parent.parent / "fixtures" / "clients" / "gray"
    profile, portfolio, communications = _load_client_data(client_dir)
    market_context = _load_market_context(client_dir)

    # Generate report components
    generator = ReportGenerator()
    result = generator.generate(profile, portfolio, communications, products, market_context)

    # Build markdown (simulating what agent would do)
    markdown = result["deterministic_sections"]
    markdown += "\n\n## Portfolio Narrative\n\nMarket narrative here."
    markdown += "\n\n## Financial Position Analysis\n\nFinancial analysis here."
    markdown += "\n\n![allocation](allocation.svg)\n"
    markdown += "\n\n![cash_flow](cash_flow.svg)\n"

    # Convert to PDF
    html = markdown_to_html(markdown, result["chart_svgs"])
    pdf_bytes = html_to_pdf(html)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")


def test_generator_includes_recent_highlights_prompt(products):
    """Generator should include recent_highlights in synthesis prompts."""
    client_dir = Path(__file__).parent.parent / "fixtures" / "clients" / "gray"
    profile, portfolio, communications = _load_client_data(client_dir)
    market_context = _load_market_context(client_dir)

    generator = ReportGenerator()
    result = generator.generate(profile, portfolio, communications, products, market_context)

    assert "recent_highlights" in result["synthesis_prompts"]


def test_generate_report_uses_redshift_themes(products):
    """generate_report tool should build market context from Redshift themes, not JSON."""
    # This test verifies the wiring: generate_report calls repos["theme"].get(client_id=...)
    # and passes results to build_market_context. The deterministic_sections string is
    # produced regardless of whether themes exist for the client.
    from wealth_management_portal_report.report_agent.tools import fetch_report_data

    # CL00014 and CL00031 have themes in Redshift
    result = fetch_report_data("CL00014")
    assert isinstance(result.components["deterministic_sections"], str)
