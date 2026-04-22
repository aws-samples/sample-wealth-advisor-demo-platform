# report

Client briefing report generator for the wealth management portal. Transforms raw portfolio data from Redshift into advisor-ready PDF reports by combining deterministic markdown sections (client summary, portfolio overview, charts) with AI-synthesised narrative sections (portfolio narrative, financial analysis, opportunities, action items). Deployed as a FastAPI service on Bedrock AgentCore Runtime.

## Architecture

The report pipeline has three stages: data fetch + transform, AI synthesis, and PDF rendering.

```
                    POST /invocations { client_id }
                                │
                                ▼
                    ┌───────────────────────┐
                    │   fetch_report_data   │
                    │   (tools.py)          │
                    └───────────┬───────────┘
                                │  MCP call: get_client_report_data
                                ▼
                    ┌───────────────────────┐
                    │  Portfolio Data Server │
                    │  (MCP via AgentCore   │
                    │   Gateway, SigV4)     │
                    └───────────┬───────────┘
                                │  raw dicts
                                ▼
              ┌─────────────────────────────────────┐
              │          transformers.py             │
              │  build_client_profile()              │
              │  build_portfolio()                   │
              │  build_communications()              │
              │  build_market_context()              │
              └─────────────────┬───────────────────┘
                                │  Pydantic models
                                ▼
              ┌─────────────────────────────────────┐
              │         ReportGenerator             │
              │  (generator.py)                     │
              │  ┌────────────────────────────────┐ │
              │  │ Deterministic sections          │ │
              │  │  client_summary (Jinja2)        │ │
              │  │  portfolio_overview (Jinja2)    │ │
              │  ├────────────────────────────────┤ │
              │  │ Synthesis prompts (8 prompts)   │ │
              │  ├────────────────────────────────┤ │
              │  │ Chart SVGs (matplotlib)         │ │
              │  │  allocation chart               │ │
              │  │  cash flow chart                │ │
              │  └────────────────────────────────┘ │
              └─────────────────┬───────────────────┘
                                │  components dict
                                ▼
              ┌─────────────────────────────────────┐
              │    Bedrock Converse (tool use)      │
              │  (agent.py — invoke_narrative_      │
              │   generator)                        │
              │  System prompt = synthesis prompts  │
              │  Forced toolChoice = submit_        │
              │   narratives (7 required string     │
              │   fields)                           │
              │  Output = narratives dict           │
              └─────────────────┬───────────────────┘
                                │  narratives
                                ▼
              ┌─────────────────────────────────────┐
              │     assemble_markdown (agent.py)    │
              │  Fill client summary placeholders,  │
              │  replace chart sentinel tokens,     │
              │  append narrative sections          │
              └─────────────────┬───────────────────┘
                                │  markdown
                                ▼
              ┌─────────────────────────────────────┐
              │           pdf.py                    │
              │  markdown → HTML (with CSS + SVGs)  │
              │  HTML → PDF (WeasyPrint)            │
              └─────────────────┬───────────────────┘
                                │  PDF bytes
                                ▼
                    ┌───────────────────────┐
                    │  S3 upload + Redshift  │
                    │  report record (MCP)   │
                    └───────────────────────┘
```

The model receives only the synthesis prompts — deterministic sections stay in Python. A forced `submit_narratives` tool call guarantees the output is a structured dict of narrative sections; `assemble_markdown` then stitches narratives + deterministic sections + chart references into the final report markdown. Bedrock-layer schema enforcement eliminates malformed-JSON parse failures; client-side validation catches empty values (which the schema does not enforce).

A separate direct Bedrock call generates a Next Best Action (NBA) recommendation independently of the main agent. NBA failure is non-fatal.

## File Structure

```
wealth_management_portal_report/
├── __init__.py                  # Public API — re-exports ReportGenerator
├── generator.py                 # ReportGenerator — renders templates + prepares prompts
├── transformers.py              # Data-layer → report-model transformations
├── charts.py                    # Matplotlib SVG chart generation
├── pdf.py                       # Markdown → HTML → PDF conversion (WeasyPrint)
├── report_style.css             # CSS for PDF styling
├── models/
│   ├── __init__.py              # Model re-exports
│   ├── client_profile.py        # ClientProfile, RiskProfile, ServiceModel, etc.
│   ├── portfolio.py             # Portfolio, Holding, Position, PerformanceMetrics, etc.
│   ├── communications.py        # Communications, Meeting, Email, Task
│   └── market_context.py        # MarketContext, MarketEvent, BenchmarkReturn
├── prompts/
│   ├── __init__.py              # Prompt re-exports
│   ├── financial_analysis.py    # Financial position analysis prompt
│   ├── portfolio_narrative.py   # Market → portfolio narrative prompt
│   ├── opportunities.py         # Cross-sell and engagement triggers prompt
│   ├── relationship_context.py  # Communication history synthesis prompt
│   ├── action_items.py          # Prioritised action items prompt
│   ├── last_interaction.py      # Recent interaction summary prompt
│   ├── recent_highlights.py     # Account highlights prompt
│   └── next_best_action.py      # Single-sentence NBA recommendation prompt
├── templates/
│   ├── __init__.py              # Template re-exports
│   ├── client_summary.py        # Jinja2 template for client summary section
│   └── portfolio_overview.py    # Jinja2 template for portfolio overview section
└── report_agent/
    ├── __init__.py              # FastAPI app setup (CORS, error handling, OpenAPI)
    ├── agent.py                 # Bedrock Converse narrative generator + final-report assembly
    ├── main.py                  # /invocations endpoint — orchestrates the full pipeline
    ├── tools.py                 # fetch_report_data, save_report_via_mcp, NBA generation
    └── Dockerfile               # Production image (python:3.12-slim + WeasyPrint deps)

tests/
├── conftest.py                  # Unit test configuration
├── unit/
│   ├── test_transformers.py     # Transformer function tests
│   ├── test_templates.py        # Template rendering tests via ReportGenerator
│   ├── test_charts.py           # SVG chart generation tests
│   ├── test_prompts.py          # Prompt structure and placeholder tests
│   └── test_pdf.py              # Markdown → HTML → PDF conversion tests
├── integration/
│   ├── conftest.py              # Integration test fixtures (env loading)
│   ├── test_report_agent.py     # End-to-end agent invocation with real Redshift data
│   ├── test_report_generation.py # Full pipeline: generator → PDF with real data
│   └── test_redshift_integration.py # Repository queries against live Redshift
└── reports/                     # Generated test report outputs (PDF + markdown)
```

## Testing

Unit tests run without external dependencies — no database, no AWS credentials:

```bash
# Run unit tests (default — integration tests excluded via pyproject.toml)
uv run pytest tests/
```

Integration tests require IAM credentials, a reachable Redshift Serverless workgroup, and `REDSHIFT_DATABASE` set:

```bash
# Run integration tests only
uv run pytest tests/integration/ -m integration
```

Via Nx:

```bash
# Unit tests (default target)
pnpm nx test wealth_management_portal.report

# Lint + format
pnpm nx lint wealth_management_portal.report
```

Docker build (ARM64 for Lambda/ECS deployment):

```bash
# Bundle + build Docker image
pnpm nx docker wealth_management_portal.report
```

Local dev server:

```bash
pnpm nx report-agent-serve wealth_management_portal.report
```

## Configuration

Set via environment variables or `.env` file at the package root:

| Variable                | Default                                          | Description                                |
|-------------------------|--------------------------------------------------|--------------------------------------------|
| `PORTFOLIO_GATEWAY_URL` | (required)                                       | AgentCore Gateway URL for MCP calls        |
| `REPORT_S3_BUCKET`      | (required)                                       | S3 bucket for generated PDF reports        |
| `REPORT_BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | Bedrock model for report synthesis and NBA |
| `REDSHIFT_DATABASE`     | `financial-advisor-db`                           | Redshift database name                     |
| `REDSHIFT_WORKGROUP`    | `financial-advisor-wg`                           | Redshift Serverless workgroup name         |
| `REDSHIFT_REGION`       | `us-west-2`                                      | AWS region for Redshift                    |
| `AWS_REGION`            | `us-east-1`                                      | AWS region for Bedrock and S3              |
| `ALLOWED_ORIGINS`       | `*`                                              | Comma-separated CORS origins               |

## Dependencies

Defined in `pyproject.toml`:

- `pydantic>=2.12.5` — data models and validation
- `jinja2>=3.1.0` — deterministic section templates
- `matplotlib>=3.8.0` — SVG chart generation
- `markdown>=3.5.0` — markdown to HTML conversion
- `weasyprint>=60.0` — HTML to PDF rendering
- `strands-agents==1.25.0` — MCP client for Portfolio Data Server (narrative generation uses Bedrock Converse directly)
- `boto3==1.42.44` — S3 upload, Bedrock runtime, SigV4 auth
- `fastapi==0.128.5` — HTTP API framework
- `uvicorn==0.40.0` — ASGI server
- `mcp==1.26.0` — MCP client for Portfolio Data Server
- `bedrock-agentcore==0.1.7` — AgentCore runtime (health check)
- `wealth_management_portal.common_auth` — SigV4 HTTPX auth (workspace dependency)

Dev/test dependencies are managed at the workspace root via `uv`.

## References

- [Strands Agents](https://github.com/strands-agents/sdk-python) — provides the MCP client used to reach the Portfolio Data Server
- [WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/) — HTML/CSS to PDF rendering engine
- [Jinja2](https://jinja.palletsprojects.com/) — template engine for deterministic report sections
- [Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) — managed agent hosting and MCP gateway
- [Nx Plugin for AWS — Python projects](https://awslabs.github.io/nx-plugin-for-aws/en/guides/python-project/) — build, test, and lint targets used by this package
