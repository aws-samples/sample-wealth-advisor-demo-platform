# Tests for chart generation
from wealth_management_portal_report.charts import (
    generate_allocation_chart,
    generate_cash_flow_chart,
)
from wealth_management_portal_report.models import (
    CashFlow,
    Holding,
    ProjectedCashFlow,
    TargetAllocation,
)


def test_allocation_chart_returns_svg():
    """Allocation chart should return valid SVG string."""
    holdings = [
        Holding(asset="US Equities", allocation=0.40, value=400000),
        Holding(asset="Fixed Income", allocation=0.60, value=600000),
    ]
    target_allocation = [
        TargetAllocation(asset="US Equities", target=0.35, lower_band=0.25, upper_band=0.45),
        TargetAllocation(asset="Fixed Income", target=0.65, lower_band=0.55, upper_band=0.75),
    ]

    svg = generate_allocation_chart(holdings, target_allocation)

    assert svg.startswith("<?xml") or svg.startswith("<svg")
    assert "</svg>" in svg
    assert "US Equities" in svg
    assert "Fixed Income" in svg


def test_cash_flow_chart_returns_svg():
    """Cash flow chart should return valid SVG string with historical and projected data."""
    cash_flows = [
        CashFlow(period="2024-Q3", inflows=10000, outflows=12000),
        CashFlow(period="2024-Q4", inflows=11000, outflows=13000),
    ]
    projected_cash_flows = [
        ProjectedCashFlow(period="2025-Q1", known_inflows=5000, estimated_outflows=12000),
        ProjectedCashFlow(period="2025-Q2", known_inflows=6000, estimated_outflows=11000),
    ]

    svg = generate_cash_flow_chart(cash_flows, projected_cash_flows)

    assert svg.startswith("<?xml") or svg.startswith("<svg")
    assert "</svg>" in svg
    assert "2024-Q3" in svg or "Q3" in svg
    assert "2025-Q1" in svg or "Q1" in svg


def test_allocation_chart_handles_empty_target():
    """Allocation chart should handle missing target allocation gracefully."""
    holdings = [
        Holding(asset="US Equities", allocation=0.50, value=500000),
    ]

    svg = generate_allocation_chart(holdings, [])

    assert svg.startswith("<?xml") or svg.startswith("<svg")
    assert "</svg>" in svg


def test_cash_flow_chart_shows_source_breakdown():
    """Cash flow chart should show stacked bars by source type for projected inflows."""
    cash_flows = [
        CashFlow(period="2024-Q4", inflows=10000, outflows=12000),
    ]
    projected_cash_flows = [
        ProjectedCashFlow(
            period="2025-Q1",
            known_inflows=5000,
            estimated_outflows=12000,
            inflow_sources={"Dividends": 3000, "Interest": 2000},
        ),
    ]

    svg = generate_cash_flow_chart(cash_flows, projected_cash_flows)

    assert "<svg" in svg
    assert "Dividends" in svg
    assert "Interest" in svg


def test_allocation_chart_renders_target_bands():
    """Allocation chart should render target bands without errors when target allocation exists."""
    holdings = [
        Holding(asset="US Equities", allocation=0.40, value=400000),
        Holding(asset="Fixed Income", allocation=0.60, value=600000),
    ]
    target_allocation = [
        TargetAllocation(asset="US Equities", target=0.35, lower_band=0.25, upper_band=0.45),
        TargetAllocation(asset="Fixed Income", target=0.65, lower_band=0.55, upper_band=0.75),
    ]

    svg = generate_allocation_chart(holdings, target_allocation)

    assert svg.startswith("<?xml") or svg.startswith("<svg")
    assert "</svg>" in svg
    assert "Target Band" in svg
