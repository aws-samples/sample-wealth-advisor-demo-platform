# Tests for template rendering
from datetime import date

from wealth_management_portal_report.generator import ReportGenerator
from wealth_management_portal_report.models import (
    ActivityLevel,
    AssociatedAccount,
    CashFlow,
    ClientProfile,
    DocumentLink,
    Holding,
    IncomeExpenseAnalysis,
    MarketContext,
    PerformanceMetrics,
    Portfolio,
    Position,
    ProjectedCashFlow,
    RiskProfile,
    ServiceModel,
    Sophistication,
    TargetAllocation,
)


def test_client_summary_includes_domicile_and_tax_jurisdiction():
    """Client summary should display domicile and tax jurisdiction."""
    profile = ClientProfile(
        client_id="TEST-001",
        names=["Test Client"],
        dates_of_birth=[date(1960, 1, 1)],
        client_since=date(2020, 1, 1),
        aum=1000000,
        risk_profile=RiskProfile.MODERATE,
        service_model=ServiceModel.ADVISORY,
        activity_level=ActivityLevel.LOW,
        sophistication=Sophistication.INTERMEDIATE,
        qualified_investor=False,
        domicile="US",
        tax_jurisdiction="US - California",
        restrictions=[],
        associated_accounts=[],
    )

    generator = ReportGenerator()
    result = generator._render_client_summary(profile)

    assert "US" in result
    assert "US - California" in result


def test_client_summary_includes_document_links():
    """Client summary should display document links as markdown."""
    profile = ClientProfile(
        client_id="TEST-001",
        names=["Test Client"],
        dates_of_birth=[date(1960, 1, 1)],
        client_since=date(2020, 1, 1),
        aum=1000000,
        risk_profile=RiskProfile.MODERATE,
        service_model=ServiceModel.ADVISORY,
        activity_level=ActivityLevel.LOW,
        sophistication=Sophistication.INTERMEDIATE,
        qualified_investor=False,
        domicile="US",
        tax_jurisdiction="US - California",
        restrictions=[],
        document_links=[
            DocumentLink(label="Investor Profile", url="https://example.com/profile.pdf"),
            DocumentLink(label="Guidelines", url="https://example.com/guidelines.pdf"),
        ],
        associated_accounts=[],
    )

    generator = ReportGenerator()
    result = generator._render_client_summary(profile)

    assert "[Investor Profile](https://example.com/profile.pdf)" in result
    assert "[Guidelines](https://example.com/guidelines.pdf)" in result


def test_client_summary_includes_restrictions_as_bullets():
    """Client summary should display restrictions as bulleted list."""
    profile = ClientProfile(
        client_id="TEST-001",
        names=["Test Client"],
        dates_of_birth=[date(1960, 1, 1)],
        client_since=date(2020, 1, 1),
        aum=1000000,
        risk_profile=RiskProfile.MODERATE,
        service_model=ServiceModel.ADVISORY,
        activity_level=ActivityLevel.LOW,
        sophistication=Sophistication.INTERMEDIATE,
        qualified_investor=False,
        domicile="US",
        tax_jurisdiction="US - California",
        restrictions=["ESG only", "No structured products"],
        associated_accounts=[],
    )

    generator = ReportGenerator()
    result = generator._render_client_summary(profile)

    assert "- ESG only" in result
    assert "- No structured products" in result


def test_client_summary_includes_last_interaction_placeholder():
    """Client summary should include placeholder for AI-synthesized last interaction."""
    profile = ClientProfile(
        client_id="TEST-001",
        names=["Test Client"],
        dates_of_birth=[date(1960, 1, 1)],
        client_since=date(2020, 1, 1),
        aum=1000000,
        risk_profile=RiskProfile.MODERATE,
        service_model=ServiceModel.ADVISORY,
        activity_level=ActivityLevel.LOW,
        sophistication=Sophistication.INTERMEDIATE,
        qualified_investor=False,
        domicile="US",
        tax_jurisdiction="US - California",
        restrictions=[],
        associated_accounts=[],
    )

    generator = ReportGenerator()
    result = generator._render_client_summary(profile)

    assert "{{ last_interaction_summary }}" in result


def test_associated_accounts_include_enriched_fields():
    """Associated accounts table should include currency, risk_profile, inception_date."""
    profile = ClientProfile(
        client_id="TEST-001",
        names=["Test Client"],
        dates_of_birth=[date(1960, 1, 1)],
        client_since=date(2020, 1, 1),
        aum=1000000,
        risk_profile=RiskProfile.MODERATE,
        service_model=ServiceModel.ADVISORY,
        activity_level=ActivityLevel.LOW,
        sophistication=Sophistication.INTERMEDIATE,
        qualified_investor=False,
        domicile="US",
        tax_jurisdiction="US - California",
        restrictions=[],
        associated_accounts=[
            AssociatedAccount(
                account_type="Brokerage",
                value=500000,
                currency="USD",
                risk_profile="Moderate",
                inception_date=date(2020, 1, 1),
            )
        ],
    )

    generator = ReportGenerator()
    result = generator._render_client_summary(profile)

    assert "USD" in result
    assert "Moderate" in result
    assert "2020-01-01" in result or "January 2020" in result


def test_portfolio_overview_includes_target_allocation_comparison():
    """Portfolio overview should show current vs target allocation with status."""
    portfolio = Portfolio(
        holdings=[
            Holding(asset="US Equities", allocation=0.40, value=400000),
            Holding(asset="Fixed Income", allocation=0.60, value=600000),
        ],
        performance=PerformanceMetrics(ytd=0.05, one_year=0.08, since_inception=0.07),
        cash_flows=[],
        income_expense_analysis=IncomeExpenseAnalysis(
            monthly_income=5000, monthly_expenses=4000, sustainability_years=30
        ),
        target_allocation=[
            TargetAllocation(asset="US Equities", target=0.35, lower_band=0.25, upper_band=0.45),
            TargetAllocation(asset="Fixed Income", target=0.65, lower_band=0.55, upper_band=0.75),
        ],
    )

    generator = ReportGenerator()
    market_context = MarketContext(
        as_of_date=date.today(), benchmark_returns=[], sector_performance=[], notable_events=[]
    )
    result = generator._render_portfolio_overview(portfolio, market_context)

    assert "Target" in result or "target" in result
    assert "40.0%" in result  # current allocation
    assert "35.0%" in result  # target allocation
    assert "✓" in result or "⚠" in result  # status indicator


def test_portfolio_overview_includes_risk_metrics():
    """Portfolio overview should display volatility and max drawdown."""
    portfolio = Portfolio(
        holdings=[Holding(asset="US Equities", allocation=1.0, value=1000000)],
        performance=PerformanceMetrics(
            ytd=0.05,
            one_year=0.08,
            since_inception=0.07,
            volatility=0.12,
            max_drawdown=-0.15,
        ),
        cash_flows=[],
        income_expense_analysis=IncomeExpenseAnalysis(
            monthly_income=5000, monthly_expenses=4000, sustainability_years=30
        ),
    )

    generator = ReportGenerator()
    market_context = MarketContext(
        as_of_date=date.today(), benchmark_returns=[], sector_performance=[], notable_events=[]
    )
    result = generator._render_portfolio_overview(portfolio, market_context)

    assert "12.0%" in result  # volatility
    assert "-15.0%" in result  # max drawdown


def test_portfolio_overview_includes_projected_cash_flows():
    """Portfolio overview should show separate historical and projected cash flow tables."""
    portfolio = Portfolio(
        holdings=[Holding(asset="US Equities", allocation=1.0, value=1000000)],
        performance=PerformanceMetrics(ytd=0.05, one_year=0.08, since_inception=0.07),
        cash_flows=[CashFlow(period="2024-Q4", inflows=10000, outflows=15000)],
        income_expense_analysis=IncomeExpenseAnalysis(
            monthly_income=5000, monthly_expenses=4000, sustainability_years=30
        ),
        projected_cash_flows=[ProjectedCashFlow(period="2025-Q1", known_inflows=5000, estimated_outflows=12000)],
    )

    generator = ReportGenerator()
    market_context = MarketContext(
        as_of_date=date.today(), benchmark_returns=[], sector_performance=[], notable_events=[]
    )
    result = generator._render_portfolio_overview(portfolio, market_context)

    assert "Historical Cash Flows" in result or "Recent Cash Flows" in result
    assert "Projected Cash Flows" in result
    assert "2024-Q4" in result
    assert "2025-Q1" in result
    assert "Known Inflows" in result or "known_inflows" in result


def test_portfolio_overview_includes_statement_of_assets():
    """Portfolio overview should include Statement of Assets with individual positions."""
    portfolio = Portfolio(
        holdings=[Holding(asset="US Equities", allocation=1.0, value=1000000)],
        performance=PerformanceMetrics(ytd=0.05, one_year=0.08, since_inception=0.07),
        cash_flows=[],
        income_expense_analysis=IncomeExpenseAnalysis(
            monthly_income=5000, monthly_expenses=4000, sustainability_years=30
        ),
        positions=[
            Position(
                ticker="VTI",
                name="Vanguard Total Stock Market",
                quantity=500,
                purchase_price=180.0,
                current_price=210.0,
                market_value=105000,
                unrealized_gain_loss=15000,
                asset_class="US Equities",
            )
        ],
    )

    generator = ReportGenerator()
    market_context = MarketContext(
        as_of_date=date.today(), benchmark_returns=[], sector_performance=[], notable_events=[]
    )
    result = generator._render_portfolio_overview(portfolio, market_context)

    assert "Statement of Assets" in result
    assert "VTI" in result
    assert "Vanguard Total Stock Market" in result
    assert "US Equities" in result


def test_client_summary_includes_recent_highlights_placeholder():
    """Client summary should include placeholder for AI-synthesized recent highlights."""
    profile = ClientProfile(
        client_id="TEST-001",
        names=["Test Client"],
        dates_of_birth=[date(1960, 1, 1)],
        client_since=date(2020, 1, 1),
        aum=1000000,
        risk_profile=RiskProfile.MODERATE,
        service_model=ServiceModel.ADVISORY,
        activity_level=ActivityLevel.LOW,
        sophistication=Sophistication.INTERMEDIATE,
        qualified_investor=False,
        domicile="US",
        tax_jurisdiction="US - California",
        restrictions=[],
        associated_accounts=[],
    )

    generator = ReportGenerator()
    result = generator._render_client_summary(profile)

    assert "Recent Highlights" in result
    assert "{{ recent_highlights }}" in result


def test_portfolio_overview_hierarchical_statement_of_assets():
    """Statement of Assets should be hierarchical by asset class with subtotals."""
    portfolio = Portfolio(
        holdings=[Holding(asset="US Equities", allocation=1.0, value=1000000)],
        performance=PerformanceMetrics(ytd=0.05, one_year=0.08, since_inception=0.07),
        cash_flows=[],
        income_expense_analysis=IncomeExpenseAnalysis(
            monthly_income=5000, monthly_expenses=4000, sustainability_years=30
        ),
        positions=[
            Position(
                ticker="VTI",
                name="Vanguard Total Stock Market",
                quantity=500,
                purchase_price=180.0,
                current_price=210.0,
                market_value=105000,
                unrealized_gain_loss=15000,
                asset_class="US Equities",
                return_pct=0.167,
                portfolio_pct=0.70,
                volatility=0.15,
                inception_date=date(2020, 1, 15),
            ),
            Position(
                ticker="BND",
                name="Vanguard Total Bond Market",
                quantity=300,
                purchase_price=80.0,
                current_price=82.0,
                market_value=24600,
                unrealized_gain_loss=600,
                asset_class="Fixed Income",
                return_pct=0.025,
                portfolio_pct=0.164,
                volatility=None,
                inception_date=None,
            ),
        ],
    )

    generator = ReportGenerator()
    market_context = MarketContext(
        as_of_date=date.today(), benchmark_returns=[], sector_performance=[], notable_events=[]
    )
    result = generator._render_portfolio_overview(portfolio, market_context)

    # Check for hierarchical structure
    assert "**US EQUITIES" in result
    assert "**FIXED INCOME" in result

    # Check for position metrics
    assert "16.7%" in result  # return %
    assert "70.0%" in result  # portfolio %
    assert "15.0%" in result  # volatility
    assert "Jan 15, 2020" in result or "2020-01-15" in result  # inception date
    assert "N/A" in result  # for missing volatility/inception date


def test_portfolio_overview_position_groups_passed_to_template():
    """Generator should pass position_groups to template with asset class subtotals."""
    portfolio = Portfolio(
        holdings=[Holding(asset="US Equities", allocation=1.0, value=1000000)],
        performance=PerformanceMetrics(ytd=0.05, one_year=0.08, since_inception=0.07),
        cash_flows=[],
        income_expense_analysis=IncomeExpenseAnalysis(
            monthly_income=5000, monthly_expenses=4000, sustainability_years=30
        ),
        positions=[
            Position(
                ticker="VTI",
                name="Vanguard Total Stock Market",
                quantity=500,
                purchase_price=180.0,
                current_price=210.0,
                market_value=105000,
                unrealized_gain_loss=15000,
                asset_class="US Equities",
                return_pct=0.167,
                portfolio_pct=0.70,
            ),
            Position(
                ticker="VXUS",
                name="Vanguard Total International Stock",
                quantity=200,
                purchase_price=60.0,
                current_price=65.0,
                market_value=13000,
                unrealized_gain_loss=1000,
                asset_class="US Equities",
                return_pct=0.083,
                portfolio_pct=0.087,
            ),
        ],
    )

    generator = ReportGenerator()
    market_context = MarketContext(
        as_of_date=date.today(), benchmark_returns=[], sector_performance=[], notable_events=[]
    )

    # Test that position_groups would be created correctly
    # This tests the grouping logic that will be implemented
    result = generator._render_portfolio_overview(portfolio, market_context)

    # Should show asset class header with subtotal
    assert "US EQUITIES" in result
    assert "$118k" in result or "118000" in result


def test_portfolio_overview_empty_positions():
    """Generator should handle empty positions gracefully."""
    portfolio = Portfolio(
        holdings=[],
        performance=PerformanceMetrics(ytd=0.05, one_year=0.08, since_inception=0.07),
        cash_flows=[],
        income_expense_analysis=IncomeExpenseAnalysis(
            monthly_income=5000, monthly_expenses=4000, sustainability_years=30
        ),
        positions=[],
    )

    generator = ReportGenerator()
    market_context = MarketContext(
        as_of_date=date.today(), benchmark_returns=[], sector_performance=[], notable_events=[]
    )

    result = generator._render_portfolio_overview(portfolio, market_context)

    # Should show total portfolio value as $0
    assert "TOTAL PORTFOLIO: $0" in result
