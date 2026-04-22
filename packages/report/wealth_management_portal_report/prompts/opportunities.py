# Opportunities prompt - identifies cross-sell and engagement triggers
OPPORTUNITIES_PROMPT = """
Identify opportunities for client engagement, cross-sell, and value-add services.

## Client Profile
{profile_json}

## Communications History
{communications_json}

## Product Catalog
{products_json}

## Your Task
Generate an "Opportunities" section that identifies:

1. **Life Event Triggers**
   - Events mentioned in communications that create planning needs
   - Example: family health issues → health fund discussion
   - Example: inheritance pending → estate planning review

2. **Product Matches**
   - Specific products from the catalog that fit this client
   - Match based on: risk profile, restrictions, situations mentioned
   - Include product name and brief rationale
   - For each recommended product, include a product sheet link: [Product Sheet](https://products.internal/PROD-XXX)

3. **Research Recommendations**
   - Generate specific, realistic research report titles with dates and dummy URLs
   - Format: [Report Title](https://research.internal/reports/slug)
   - Examples: "Q1 2026 Tech Sector Outlook", "Fixed Income Strategy in Rising Rate Environment"
   - Match based on topics discussed or situations identified

## Income Coverage Analysis
- If portfolio data shows income coverage ratio < 100% (known inflows < estimated outflows in
  projected cash flows), reference the Financial Goals Sustainability Assessment and note
  de-capitalisation risk as context for product recommendations

## Guidelines
- Every opportunity must link to something specific in the communications
- Frame opportunities as client benefits, not sales pitches
- Include the product/research ID for reference
- Prioritize by relevance and timeliness
- Format as markdown with clear categories
"""
