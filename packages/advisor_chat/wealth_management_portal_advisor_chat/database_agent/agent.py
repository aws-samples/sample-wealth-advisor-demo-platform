"""Database Agent — answers questions about clients, portfolios, and holdings."""

import os

from strands import Agent
from strands.models.bedrock import BedrockModel

from wealth_management_portal_advisor_chat.common.memory import create_ltm_session_manager
from wealth_management_portal_advisor_chat.common.schema import get_schema
from wealth_management_portal_advisor_chat.common.sql_tool import run_sql

from .tools import get_client_report_pdf

SYSTEM_PROMPT_TEMPLATE = """

Generate database query prompt with the loaded schema.

Returns:
Formatted prompt string with schema information if available

use the following database schema to understand the table structure and generate SQL to retrieve the most accurate data:

{schema}

## Output Format Requirements:

### 1. Structured Data Presentation
**Summary Format:**
```
## Portfolio Overview
- **Total Portfolio Value**: $X,XXX,XXX
- **Asset Allocation**: [Breakdown by major asset classes]
- **YTD Performance**: X.XX% (vs. Benchmark: X.XX%)
- **Risk Level**: [Conservative/Moderate/Aggressive]
- **Last Updated**: [Date and Time]
```

**Detailed Holdings Table:**
```
| Security | Quantity | Market Value | % of Portfolio | YTD Return | Risk Rating |
|----------|----------|--------------|----------------|------------|-------------|
| [Name]   | [Qty]    | $XXX,XXX     | XX.X%         | +/-X.X%    | [Rating]    |
```

**Asset Allocation Analysis:**
```
| Sector Name        | Allocation      | Stock/ETF Name 
|-------------------|------------------|--------------|
| Technology Sector | X.XX%            | MSFT + NVDA | 
| Broder Market ETF | X.XX%            | SPY      | 
```

**Performance Analysis:**
```
| Period    | Portfolio Return | Benchmark Return | Relative Performance | Risk Metrics |
|-----------|------------------|------------------|---------------------|--------------|
| 1 Month   | X.XX%           | X.XX%            | +/-X.XX%           | [Metrics]    |
| YTD       | X.XX%           | X.XX%            | +/-X.XX%           | [Metrics]    |
```




### 2. Investment Summary Guidelines
**Portfolio Return Analysis:**
- Overall investment performance summary with key drivers
- Asset class contribution analysis and attribution
- Risk-adjusted performance evaluation
- Comparison to client objectives and market benchmarks
- Identification of top and bottom performing holdings

Your database query capabilities serve as the foundation for informed
investment advice, comprehensive client service, and effective portfolio
management in the financial advisory process.

--
"""

TOOLS = [run_sql, get_client_report_pdf]


def create_agent(session_id: str = "") -> Agent:
    schema = get_schema(["client_search", "advisor_master", "client_restrictions", "client_portfolio_holdings"])
    kwargs: dict = {
        "name": "Database Agent",
        "description": "Search clients, view profiles, portfolio holdings, and AUM trends.",
        "model": BedrockModel(
            model_id=os.environ.get("SUBAGENT_BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
        ),
        "system_prompt": SYSTEM_PROMPT_TEMPLATE.format(schema=schema),
        "tools": TOOLS,
        "callback_handler": None,
    }
    if session_id:
        sm = create_ltm_session_manager(session_id)
        if sm:
            kwargs["session_manager"] = sm
    return Agent(**kwargs)
