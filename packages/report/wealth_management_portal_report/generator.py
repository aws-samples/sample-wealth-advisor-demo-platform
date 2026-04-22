# Report generator - prepares deterministic sections and synthesis prompts
import json
from datetime import date

from jinja2 import Template

from wealth_management_portal_report.models import (
    ClientProfile,
    Communications,
    MarketContext,
    Portfolio,
    TargetAllocation,
)

from .charts import generate_allocation_chart, generate_cash_flow_chart
from .prompts import (
    ACTION_ITEMS_PROMPT,
    FINANCIAL_ANALYSIS_PROMPT,
    LAST_INTERACTION_PROMPT,
    OPPORTUNITIES_PROMPT,
    PORTFOLIO_NARRATIVE_PROMPT,
    RECENT_HIGHLIGHTS_PROMPT,
    RELATIONSHIP_CONTEXT_PROMPT,
)
from .templates import CLIENT_SUMMARY_TEMPLATE, PORTFOLIO_OVERVIEW_TEMPLATE


class ReportGenerator:
    """
    Prepares client briefing reports by rendering deterministic sections
    and preparing prompts for AI synthesis.
    """

    def generate(
        self,
        profile: ClientProfile,
        portfolio: Portfolio,
        communications: Communications,
        products: list[dict],
        market_context: MarketContext,
    ) -> dict:
        """
        Generate report components.

        Returns:
            Dictionary with:
            - deterministic_sections: Rendered markdown
            - synthesis_prompts: Dict of prompts for AI to complete
            - chart_svgs: Dict of chart names to SVG strings
        """
        # Render deterministic sections
        client_summary = self._render_client_summary(profile)
        portfolio_overview = self._render_portfolio_overview(portfolio, market_context)

        # Generate charts
        allocation_chart = generate_allocation_chart(portfolio.holdings, portfolio.target_allocation)
        cash_flow_chart = generate_cash_flow_chart(portfolio.cash_flows, portfolio.projected_cash_flows)

        # Prepare synthesis prompts
        synthesis_prompts = {
            "last_interaction_summary": LAST_INTERACTION_PROMPT.format(
                profile_json=profile.model_dump_json(indent=2),
                communications_json=communications.model_dump_json(indent=2),
            ),
            "recent_highlights": RECENT_HIGHLIGHTS_PROMPT.format(
                profile_json=profile.model_dump_json(indent=2),
                portfolio_json=portfolio.model_dump_json(indent=2),
                communications_json=communications.model_dump_json(indent=2),
            ),
            "portfolio_narrative": PORTFOLIO_NARRATIVE_PROMPT.format(
                market_context_json=market_context.model_dump_json(indent=2),
                portfolio_json=portfolio.model_dump_json(indent=2),
            ),
            "financial_analysis": FINANCIAL_ANALYSIS_PROMPT.format(
                profile_json=profile.model_dump_json(indent=2),
                portfolio_json=portfolio.model_dump_json(indent=2),
            ),
            "opportunities": OPPORTUNITIES_PROMPT.format(
                profile_json=profile.model_dump_json(indent=2),
                communications_json=communications.model_dump_json(indent=2),
                products_json=json.dumps(
                    [p.model_dump(mode="json") if hasattr(p, "model_dump") else p for p in products],
                    indent=2,
                    default=str,
                ),
            ),
            "relationship_context": RELATIONSHIP_CONTEXT_PROMPT.format(
                profile_json=profile.model_dump_json(indent=2),
                communications_json=communications.model_dump_json(indent=2),
            ),
            "action_items": ACTION_ITEMS_PROMPT.format(
                profile_json=profile.model_dump_json(indent=2),
                portfolio_json=portfolio.model_dump_json(indent=2),
                communications_json=communications.model_dump_json(indent=2),
            ),
        }

        return {
            "deterministic_sections": f"{client_summary}\n\n{portfolio_overview}",
            "synthesis_prompts": synthesis_prompts,
            "chart_svgs": {
                "allocation": allocation_chart,
                "cash_flow": cash_flow_chart,
            },
        }

    def _render_client_summary(self, profile: ClientProfile) -> str:
        """Render client summary from template."""
        today = date.today()
        context = {
            "names": profile.names,
            "ages": [self._calculate_age(dob, today) for dob in profile.dates_of_birth],
            "client_since": profile.client_since.strftime("%B %Y"),
            "tenure_years": today.year - profile.client_since.year,
            "aum_formatted": self._format_currency(profile.aum),
            "risk_profile": profile.risk_profile.value,
            "service_model": profile.service_model.value,
            "activity_level": profile.activity_level.value,
            "sophistication": profile.sophistication.value,
            "domicile": profile.domicile,
            "tax_jurisdiction": profile.tax_jurisdiction,
            "qualified_investor": profile.qualified_investor,
            "restrictions": profile.restrictions,
            "document_links": [{"label": d.label, "url": d.url} for d in profile.document_links]
            or [
                {
                    "label": "Investor Profile",
                    "url": f"https://docs.internal/clients/{profile.client_id}/investor-profile",
                },
                {
                    "label": "Investment Guidelines",
                    "url": f"https://docs.internal/clients/{profile.client_id}/investment-guidelines",
                },
                {"label": "Client Brochure", "url": f"https://docs.internal/clients/{profile.client_id}/brochure"},
            ],
            "associated_accounts": [
                {
                    "account_type": a.account_type,
                    "value_formatted": self._format_currency(a.value),
                    "currency": a.currency,
                    "risk_profile": a.risk_profile,
                    "inception_date_formatted": (a.inception_date.strftime("%B %Y") if a.inception_date else None),
                }
                for a in profile.associated_accounts
            ],
            "last_interaction_summary": "{{ last_interaction_summary }}",
            "recent_highlights": "{{ recent_highlights }}",
        }
        return Template(CLIENT_SUMMARY_TEMPLATE).render(**context)

    def _render_portfolio_overview(self, portfolio: Portfolio, market_context: MarketContext) -> str:
        """Render portfolio overview from template."""
        # Build target allocation lookup
        target_lookup = {t.asset: t for t in portfolio.target_allocation}

        # Group positions by asset class for hierarchical display
        position_groups = []
        total_portfolio_value = sum(p.market_value for p in portfolio.positions)

        # Group positions by asset class
        asset_class_groups = {}
        for position in portfolio.positions:
            asset_class = position.asset_class
            if asset_class not in asset_class_groups:
                asset_class_groups[asset_class] = []
            asset_class_groups[asset_class].append(position)

        # Create position groups with subtotals
        for asset_class, positions in asset_class_groups.items():
            group_total_value = sum(p.market_value for p in positions)
            group_total_pct = group_total_value / total_portfolio_value if total_portfolio_value > 0 else 0

            position_groups.append(
                {
                    "asset_class": asset_class,
                    "total_value": group_total_value,
                    "total_value_formatted": self._format_currency(group_total_value),
                    "total_pct": f"{group_total_pct * 100:.1f}%",
                    "positions": [
                        {
                            "ticker": p.ticker,
                            "name": p.name,
                            "portfolio_pct": f"{p.portfolio_pct * 100:.1f}%" if p.portfolio_pct is not None else "N/A",
                            "market_value_formatted": self._format_currency(p.market_value),
                            "return_pct": f"{p.return_pct * 100:.1f}%" if p.return_pct is not None else "N/A",
                            "volatility": f"{p.volatility * 100:.1f}%" if p.volatility is not None else "N/A",
                            "inception_date_formatted": (
                                p.inception_date.strftime("%b %d, %Y") if p.inception_date else "N/A"
                            ),
                        }
                        for p in positions
                    ],
                }
            )

        context = {
            "market_events": [
                {
                    "date": e.date.strftime("%b %d, %Y"),
                    "description": e.description,
                    "impact": e.impact,
                }
                for e in market_context.notable_events
            ],
            "holdings": [
                {
                    "asset": h.asset,
                    "allocation_pct": f"{h.allocation * 100:.1f}%",
                    "value_formatted": self._format_currency(h.value),
                    "target_pct": (
                        f"{target_lookup[h.asset].target * 100:.1f}%" if h.asset in target_lookup else "N/A"
                    ),
                    "band": (
                        f"{target_lookup[h.asset].lower_band * 100:.0f}%-{target_lookup[h.asset].upper_band * 100:.0f}%"
                        if h.asset in target_lookup
                        else "N/A"
                    ),
                    "status": self._allocation_status(h.allocation, target_lookup.get(h.asset)),
                }
                for h in portfolio.holdings
            ],
            "performance": {
                "ytd_pct": f"{portfolio.performance.ytd * 100:.1f}%",
                "one_year_pct": f"{portfolio.performance.one_year * 100:.1f}%",
                "since_inception_pct": f"{portfolio.performance.since_inception * 100:.1f}%",
                "volatility_pct": (
                    f"{portfolio.performance.volatility * 100:.1f}%"
                    if portfolio.performance.volatility is not None
                    else "N/A"
                ),
                "max_drawdown_pct": (
                    f"{portfolio.performance.max_drawdown * 100:.1f}%"
                    if portfolio.performance.max_drawdown is not None
                    else "N/A"
                ),
            },
            "cash_flows": [
                {
                    "period": cf.period,
                    "inflows_formatted": self._format_currency(cf.inflows),
                    "outflows_formatted": self._format_currency(cf.outflows),
                    "net_formatted": self._format_currency(cf.inflows - cf.outflows),
                }
                for cf in portfolio.cash_flows
            ],
            "projected_cash_flows": [
                {
                    "period": pcf.period,
                    "dividends": self._format_currency(pcf.inflow_sources.get("dividends", 0)),
                    "interest": self._format_currency(pcf.inflow_sources.get("interest", 0)),
                    "coupons": self._format_currency(pcf.inflow_sources.get("coupons", 0)),
                    "known_inflows_formatted": self._format_currency(pcf.known_inflows),
                    "estimated_outflows_formatted": self._format_currency(pcf.estimated_outflows),
                    "net_formatted": self._format_currency(pcf.known_inflows - pcf.estimated_outflows),
                }
                for pcf in portfolio.projected_cash_flows
            ],
            "projected_portfolio_values": [
                {
                    "period": ppv.period,
                    "conservative_formatted": self._format_currency(ppv.conservative),
                    "base_formatted": self._format_currency(ppv.base),
                    "optimistic_formatted": self._format_currency(ppv.optimistic),
                }
                for ppv in portfolio.projected_portfolio_values
            ],
            "position_groups": position_groups,
            "total_portfolio_value_formatted": self._format_currency(total_portfolio_value),
        }
        return Template(PORTFOLIO_OVERVIEW_TEMPLATE).render(**context)

    @staticmethod
    def _allocation_status(current: float, target: TargetAllocation | None) -> str:
        """Determine if allocation is within target band."""
        if not target:
            return "N/A"
        if target.lower_band <= current <= target.upper_band:
            return "✓"
        deviation = abs(current - target.target) * 100
        return f"⚠ {deviation:.1f}%"

    @staticmethod
    def _calculate_age(dob: date, today: date) -> int:
        """Calculate age from date of birth."""
        age = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        return age

    @staticmethod
    def _format_currency(value: float) -> str:
        """Format currency as $X.XXM or $XXXk."""
        if value >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value / 1_000:.0f}k"
        elif value == 0:
            return "$0"
        else:
            return f"${value:,.0f}"
