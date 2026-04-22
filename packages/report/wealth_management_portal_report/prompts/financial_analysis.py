# Financial analysis prompt - interprets portfolio sustainability
FINANCIAL_ANALYSIS_PROMPT = """
Analyze the client's financial position and provide actionable insights.

## Client Profile
{profile_json}

## Portfolio Data
{portfolio_json}

## Your Task
Generate a "Financial Position Analysis" section that includes:

1. **Financial Goals Sustainability Assessment**
   - Compute and prominently state income coverage ratio = sum(known_inflows) /
     sum(estimated_outflows) from projected cash flows
   - If coverage ratio < 100%, this is critical - lead with it and state minimum
     portfolio return required to avoid de-capitalisation
   - Current monthly income vs expenses
   - How long the current pattern can be projected to be maintained under current conditions
   - Whether this is estimated to be healthy, concerning, or critical based on current assumptions
   - Reference risk metrics (volatility, max drawdown) in context of sustainability projections
   - Include benchmark comparison for returns (e.g., "portfolio returned X% vs S&P 500 Y%").
     If benchmark_returns data is empty, use well-known index returns as reference points

2. **Allocation Analysis**
   - Current allocation vs target allocation
   - Distinguish between allocation drift due to market movements (normal, expected) and intentional positioning
   - Only flag rebalancing need when allocation is OUTSIDE the target bands, not merely drifted from the exact target
   - If rebalancing is recommended, specify which asset classes to adjust, the direction
     (increase/decrease), and approximate magnitude
   - Do NOT recommend rebalancing purely because allocation drifted within bands
   - Any positions outside target bands
   - Implications for projected risk and return expectations

3. **Cash Flow Projections**
   - Review projected cash flows (known inflows and estimated outflows)
   - Identify any upcoming changes in cash flow patterns estimated under current conditions
   - Impact on portfolio sustainability projections

4. **Scenario Projections** (if sustainability < 30 years)
   - What is projected to happen if portfolio drops 20%
   - What withdrawal rate would be estimated as sustainable
   - Trade-off options: reduce spending vs. increase risk vs. add capital

5. **Capacity Assessment** (if sustainability > 30 years)
   - Surplus capacity identified under current assumptions
   - Opportunities: legacy planning, charitable giving, lifestyle enhancement
   - Frame positively without advising to "spend more"

## Guidelines
- Back every statement with numbers from the data
- Reference target allocation, projected cash flows, volatility, and max drawdown where relevant
- Never say "you can spend more" - instead identify "capacity for additional goals"
- If situation is concerning, present options neutrally without alarm
- Use professional, factual tone with hedged language for all projections
- Soften all projection language with "Based on current assumptions, subject to changes in
  portfolio value, inflows/outflows, returns, volatility, drawdowns, and their timing"
- Avoid strong certainty statements; prefer "projected", "estimated", "under current conditions"
- Format as markdown with clear headers
"""
