# scheduler-tools

Lambda functions for scheduled batch operations in the wealth management portal. Contains four handlers — client list retrieval, report generation, general theme generation, and portfolio theme generation — orchestrated by two Step Functions state machines and triggered by EventBridge schedules.

## Architecture

Two Step Functions state machines share the `get_client_list` Lambda for client enumeration, then fan out to their respective processing Lambdas:

```
EventBridge (daily at 2 AM UTC)
  │
  ├─> Report Scheduler (Step Function)
  │     ├─> get_client_list ──> Redshift (paginate all client IDs)
  │     │     Returns: test_client_ids (first 3), remaining_client_ids (rest)
  │     │
  │     ├─> Canary: Map (test_client_ids, sequential, fail-fast)
  │     │     └─> generate_report ──> AgentCore invoke_agent_runtime
  │     │
  │     └─> Full Batch: Map (remaining_client_ids, max 10 concurrent)
  │           └─> generate_report ──> AgentCore invoke_agent_runtime
  │
  └─> Theme Scheduler (Step Function)
        ├─> generate_general_themes ──> Web Crawler MCP (crawl + generate)
        │
        ├─> get_client_list ──> Redshift (same Lambda, shared)
        │
        ├─> Canary: Map (test_client_ids, sequential, fail-fast)
        │     └─> generate_portfolio_themes ──> Web Crawler MCP
        │
        └─> Full Batch: Map (remaining_client_ids, max 10 concurrent)
              └─> generate_portfolio_themes ──> Web Crawler MCP
```

Both state machines use a canary pattern: the first 3 clients run sequentially and any failure aborts the entire run, preventing a broken pipeline from spawning 100+ parallel invocations.

### Lambda Handlers

| Handler                      | Purpose                                              | Invokes                          | Timeout | Memory |
|------------------------------|------------------------------------------------------|----------------------------------|---------|--------|
| `get_client_list`            | Paginate Redshift for all client IDs, split into batches | Redshift Data API via `ClientRepository` | 30s     | 256 MB |
| `generate_report`            | Generate a PDF report for a single client            | Report agent via AgentCore SDK   | 300s    | 512 MB |
| `generate_general_themes`    | Crawl articles and generate general market themes    | Web Crawler MCP (2 tool calls)   | 900s    | 512 MB |
| `generate_portfolio_themes`  | Generate portfolio-specific themes for a single client | Web Crawler MCP (1 tool call)    | 900s    | 512 MB |

## File Structure

```
wealth_management_portal_scheduler_tools/
├── __init__.py
└── lambda_functions/
    ├── get_client_list.py            # Paginate Redshift, split into test + remaining batches
    ├── generate_report.py            # Invoke report agent via AgentCore SDK
    ├── generate_general_themes.py    # Crawl articles + generate market themes via MCP
    └── generate_portfolio_themes.py  # Generate per-client portfolio themes via MCP

tests/
├── conftest.py
└── unit/
    ├── __init__.py
    ├── test_get_client_list.py            # Pagination, batch splitting, edge cases
    ├── test_generate_report.py            # AgentCore invocation, error handling
    ├── test_generate_general_themes.py    # MCP tool calls, crawl failure resilience
    └── test_generate_portfolio_themes.py  # MCP tool calls, env var handling

tests/  (top-level, outside scheduler_tools/)
├── test_generate_general_themes_lambda.py     # MCP client integration tests
└── test_generate_portfolio_themes_lambda.py   # MCP client integration tests
```

## Testing

Unit tests mock all external dependencies (Redshift, AgentCore, MCP):

```bash
# Run unit tests (from package root)
cd packages/scheduler-tools/scheduler_tools
uv run pytest tests/

# Via Nx
pnpm nx test wealth_management_portal.scheduler_tools
```

Top-level integration tests exercise the MCP client wiring with mocked transport:

```bash
cd packages/scheduler-tools
uv run pytest tests/
```

Lint and format:

```bash
pnpm nx lint wealth_management_portal.scheduler_tools
pnpm nx format wealth_management_portal.scheduler_tools
```

## Configuration

Set via environment variables (injected by CDK in `application-stack.ts`):

| Variable              | Handler(s)                                       | Description                                |
|-----------------------|--------------------------------------------------|--------------------------------------------|
| `REDSHIFT_WORKGROUP`  | `get_client_list`                                | Redshift Serverless workgroup name         |
| `REDSHIFT_DATABASE`   | `get_client_list`                                | Redshift database name                     |
| `REPORT_AGENT_ARN`    | `generate_report`                                | AgentCore runtime ARN for the report agent |
| `WEB_CRAWLER_MCP_ARN` | `generate_general_themes`, `generate_portfolio_themes` | AgentCore runtime ARN for Web Crawler MCP  |
| `TOP_N_STOCKS`        | `generate_portfolio_themes`                      | Number of top holdings to analyze (default 5) |
| `THEMES_PER_STOCK`    | `generate_portfolio_themes`                      | Themes to generate per stock (default 2)   |
| `THEME_HOURS`         | `generate_general_themes`, `generate_portfolio_themes` | Lookback window in hours (default 48)      |
| `THEME_LIMIT`         | `generate_general_themes`                        | Max general themes to generate (default 6) |
| `POWERTOOLS_SERVICE_NAME` | All                                          | Service name for structured logging        |
| `LOG_LEVEL`           | All                                              | Log level (default INFO)                   |

## Dependencies

Defined in `pyproject.toml`:

- `aws-lambda-powertools==3.24.0` — structured logging, tracing, and Lambda utilities
- `wealth_management_portal.portfolio_data_access` — `ClientRepository` for Redshift queries
- `wealth_management_portal.common_auth` — `SigV4HTTPXAuth` for MCP client authentication
- `mcp` — MCP protocol client for tool invocation
- `httpx` — HTTP transport for MCP streamable-HTTP connections
- `strands-agents` — `MCPClient` wrapper for MCP tool calls
- `boto3` (Lambda runtime) — AgentCore SDK, Redshift Data API, SES credentials

## References

- [AWS Lambda Powertools for Python](https://docs.powertools.aws.dev/lambda/python/latest/) — structured logging, tracing, and typing utilities
- [Redshift Serverless](https://docs.aws.amazon.com/redshift/latest/mgmt/serverless-whatis.html) — workgroup and namespace concepts
- [Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) — agent runtime invocation and gateway patterns
- [Nx Plugin for AWS — Python projects](https://awslabs.github.io/nx-plugin-for-aws/en/guides/python-project/) — build, test, and lint targets used by this package
