# ruff: noqa: E501
# Portfolio overview template
PORTFOLIO_OVERVIEW_TEMPLATE = """
{%- if market_events %}
## Market Context
| Date | Event | Impact |
|------|-------|--------|
{%- for e in market_events %}
| {{ e.date }} | {{ e.description }} | {{ e.impact }} |
{%- endfor %}

{%- endif %}
## Portfolio Overview

### Asset Allocation
| Asset Class | Current % | Current Value | Target % | Band | Status |
|-------------|-----------|---------------|----------|------|--------|
{%- for h in holdings %}
| {{ h.asset }} | {{ h.allocation_pct }} | {{ h.value_formatted }} | {{ h.target_pct }} | {{ h.band }} | {{ h.status }} |
{%- endfor %}

<!-- CHART:allocation -->

### Performance
| Period | Return | Volatility | Max Drawdown |
|--------|--------|------------|--------------|
| YTD | {{ performance.ytd_pct }} | {{ performance.volatility_pct }} | {{ performance.max_drawdown_pct }} |
| 1-Year | {{ performance.one_year_pct }} | {{ performance.volatility_pct }} | {{ performance.max_drawdown_pct }} |
| Since Inception | {{ performance.since_inception_pct }} | {{ performance.volatility_pct }} | {{ performance.max_drawdown_pct }} |

### Recent Cash Flows
| Period | Inflows | Outflows | Net |
|--------|---------|----------|-----|
{%- for cf in cash_flows %}
| {{ cf.period }} | {{ cf.inflows_formatted }} | {{ cf.outflows_formatted }} | {{ cf.net_formatted }} |
{%- endfor %}

<!-- CHART:cash_flow -->

### Projected Cash Flows
| Period | Dividends | Interest | Coupons | Known Inflows | Estimated Outflows | Net |
|--------|-----------|----------|---------|---------------|--------------------|-----|
{%- for pcf in projected_cash_flows %}
| {{ pcf.period }} | {{ pcf.dividends }} | {{ pcf.interest }} | {{ pcf.coupons }} | {{ pcf.known_inflows_formatted }} | {{ pcf.estimated_outflows_formatted }} | {{ pcf.net_formatted }} |
{%- endfor %}

### Projected Portfolio Value
| Period | Conservative | Base Case | Optimistic |
|--------|--------------|-----------|------------|
{%- for ppv in projected_portfolio_values %}
| {{ ppv.period }} | {{ ppv.conservative_formatted }} | {{ ppv.base_formatted }} | {{ ppv.optimistic_formatted }} |
{%- endfor %}

### Statement of Assets
{%- if position_groups %}
{%- for group in position_groups %}
**{{ group.asset_class|upper }} ({{ group.total_pct }} of portfolio, {{ group.total_value_formatted }})**

| Ticker | Name | Portfolio % | Market Value | Return % | Volatility | Held Since |
|--------|------|-------------|--------------|----------|------------|------------|
{%- for p in group.positions %}
| {{ p.ticker }} | {{ p.name }} | {{ p.portfolio_pct }} | {{ p.market_value_formatted }} | {{ p.return_pct }} | {{ p.volatility }} | {{ p.inception_date_formatted }} |
{%- endfor %}

{%- endfor %}
{%- endif %}

**TOTAL PORTFOLIO: {{ total_portfolio_value_formatted }}**
"""
