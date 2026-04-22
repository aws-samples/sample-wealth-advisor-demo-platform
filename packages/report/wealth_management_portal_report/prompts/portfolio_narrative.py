# Portfolio narrative prompt - synthesizes market context, portfolio impact, and actions taken
PORTFOLIO_NARRATIVE_PROMPT = """
Synthesize a narrative that connects market events to portfolio performance and actions taken.

## Market Context
{market_context_json}

## Portfolio Data
{portfolio_json}

## Your Task
Generate a "Portfolio Narrative" section with exactly 4 subsections using markdown ### headers:

### Executive Summary
2-3 sentence overview of portfolio status and key takeaway for the period.

### Market Performance
Key market events, benchmark moves, and sector trends. EVERY data point must include its
reference period (e.g., "8.5% annualised volatility (YTD)", "24.2% return (1-year)").

### Portfolio Performance
How market movements affected this portfolio. Must include at least 2 specific instrument
callouts by name with their individual return contribution and performance impact.

### Asset Allocation
Current vs target positioning, any rebalancing actions taken with specifics (which allocations
changed, by how much, what triggered it). Note that allocation drift within target bands is
expected in active management.

## Requirements
- Format as markdown with ### subsection headers
- EVERY data point must include its reference period
- Call out at least 2 specific instruments by name with performance contribution
- Include specific rebalancing details: what changed, why, and by how much
- Acknowledge that allocation drift within bands is normal in active management
- Professional, factual tone
- Use specific numbers from the data provided
"""
