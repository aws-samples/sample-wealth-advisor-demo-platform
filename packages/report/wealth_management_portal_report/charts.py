# Chart generation using matplotlib
import io

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt

from wealth_management_portal_report.models import (
    CashFlow,
    Holding,
    ProjectedCashFlow,
    TargetAllocation,
)


def generate_allocation_chart(holdings: list[Holding], target_allocation: list[TargetAllocation]) -> str:
    """Generate asset allocation chart comparing current vs target."""
    # Build target lookup
    target_lookup = {t.asset: t.target for t in target_allocation}

    # Build band lookup for target ranges
    band_lookup = {t.asset: (t.lower_band * 100, t.upper_band * 100) for t in target_allocation}

    # Prepare data
    assets = [h.asset for h in holdings]
    current = [h.allocation * 100 for h in holdings]
    target = [target_lookup.get(h.asset, 0) * 100 for h in holdings]

    # Create chart
    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(assets))
    width = 0.35

    # Draw target bands behind bars
    if target_allocation:
        for i, asset in enumerate(assets):
            if asset in band_lookup:
                lower, upper = band_lookup[asset]
                ax.fill_between([i - 0.4, i + 0.4], lower, upper, alpha=0.15, color="grey", zorder=1)

        # Add target band to legend (draw invisible bar for legend entry)
        ax.bar([], [], alpha=0.15, color="grey", label="Target Band")

    ax.bar([i - width / 2 for i in x], current, width, label="Current", color="#2E86AB", zorder=2)
    if target_allocation:
        ax.bar([i + width / 2 for i in x], target, width, label="Target", color="#A23B72", zorder=2)

    ax.set_ylabel("Allocation (%)")
    ax.set_title("Asset Allocation")
    ax.set_xticks(x)
    ax.set_xticklabels(assets, rotation=45, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    # Convert to SVG
    buf = io.BytesIO()
    plt.savefig(buf, format="svg")
    plt.close(fig)
    buf.seek(0)
    return buf.read().decode("utf-8")


def generate_cash_flow_chart(cash_flows: list[CashFlow], projected_cash_flows: list[ProjectedCashFlow]) -> str:
    """Generate cash flow chart with historical and projected periods."""
    # Prepare data
    periods = [cf.period for cf in cash_flows] + [pcf.period for pcf in projected_cash_flows]
    historical_count = len(cash_flows)

    # Create chart
    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(periods))
    width = 0.35

    # Historical inflows and outflows (solid)
    historical_inflows = [cf.inflows / 1000 for cf in cash_flows]
    historical_outflows = [-cf.outflows / 1000 for cf in cash_flows]

    ax.bar(
        x[:historical_count],
        historical_inflows,
        width,
        label="Inflows (Historical)",
        color="#06A77D",
    )
    ax.bar(
        x[:historical_count],
        historical_outflows,
        width,
        label="Outflows (Historical)",
        color="#D62246",
    )

    # Projected outflows (hatched)
    if projected_cash_flows:
        projected_outflows = [-pcf.estimated_outflows / 1000 for pcf in projected_cash_flows]
        ax.bar(
            x[historical_count:],
            projected_outflows,
            width,
            label="Outflows (Projected)",
            color="#D62246",
            alpha=0.6,
            hatch="//",
        )

        # Collect all unique source types from projected cash flows
        all_sources = set()
        for pcf in projected_cash_flows:
            all_sources.update(pcf.inflow_sources.keys())
        all_sources = sorted(list(all_sources))

        # Color palette for sources
        source_colors = {
            "Dividends": "#2E8B57",  # Sea green
            "Interest": "#4682B4",  # Steel blue
            "Coupons": "#FF8C00",  # Dark orange
        }

        # Stack projected inflows by source
        if all_sources:
            bottoms = [0] * len(projected_cash_flows)
            for source in all_sources:
                source_values = []
                for pcf in projected_cash_flows:
                    value = pcf.inflow_sources.get(source, 0) / 1000
                    source_values.append(value)

                color = source_colors.get(source, "#06A77D")
                ax.bar(
                    x[historical_count:],
                    source_values,
                    width,
                    bottom=bottoms,
                    label=f"{source} (Projected)",
                    color=color,
                    alpha=0.7,
                    hatch="//",
                )

                # Update bottoms for next stack
                for i in range(len(bottoms)):
                    bottoms[i] += source_values[i]

    ax.set_ylabel("Cash Flow ($k)")
    ax.set_title("Cash Flows")
    ax.set_xticks(x)
    ax.set_xticklabels(periods, rotation=45, ha="right")
    ax.axhline(y=0, color="black", linewidth=0.8)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    # Convert to SVG
    buf = io.BytesIO()
    plt.savefig(buf, format="svg")
    plt.close(fig)
    buf.seek(0)
    return buf.read().decode("utf-8")
