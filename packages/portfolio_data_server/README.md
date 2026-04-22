# portfolio_data_server

Lambda-based data gateway for the wealth management portal. Exposes portfolio data operations as tools via an AgentCore Gateway backed by AWS Lambda. Consumers (report agent, web crawler) connect over MCP-over-HTTP with SigV4 auth — the Gateway handles MCP protocol translation, and the Lambda executes queries against Redshift Serverless using the `portfolio_data_access` library.

## Architecture

The module contains two Lambda functions behind an AgentCore Gateway:

```
┌──────────────────────────────────────────────────────┐
│                    Consumers                         │
│  (report agent, web crawler, advisor chat agents)    │
└──────────────────────┬───────────────────────────────┘
                       │ MCP over streamable-http (SigV4)
                       ▼
┌──────────────────────────────────────────────────────┐
│               AgentCore Gateway                      │
│  - IAM authorization                                 │
│  - MCP protocol handling (automatic)                 │
│  - Tool schema defines available tools               │
└──────────┬───────────────────────────────────────────┘
           │ Lambda invocation
           ▼
┌──────────────────────────────────────────────────────┐
│            Lambda Functions                           │
│                                                      │
│  portfolio_data_gateway.py                           │
│  - 11 tools (CRUD for clients, reports, articles,    │
│    themes, holdings)                                 │
│  - Dispatch table routes by bedrockAgentCoreToolName │
│  - SQLAlchemy QueuePool for connection reuse         │
│  - Async parallel fetch for report data              │
│                                                      │
│  smart_chat_data_access.py                           │
│  - execute_sql tool for advisor chat agents          │
│  - Parameterized query execution (:p0, :p1 syntax)  │
└──────────────────────┬───────────────────────────────┘
                       │ IAM-authenticated SQL
                       ▼
┌──────────────────────────────────────────────────────┐
│              Redshift Serverless                     │
│           financial-advisor-wg                       │
└──────────────────────────────────────────────────────┘
```

- **portfolio_data_gateway** — main gateway Lambda with 11 tools dispatched via a `_DISPATCH` table. The Gateway extracts the tool name from `context.client_context.custom["bedrockAgentCoreToolName"]` (format: `{targetId}___toolName`). Uses `asyncio.gather` for parallel Redshift queries in `get_client_report_data`.
- **smart_chat_data_access** — standalone Lambda for advisor chat agents. Accepts raw SQL with positional parameters (`:p0`, `:p1`) and returns result rows as dicts.
- **utils.py** — shared serialization helpers for `date` → ISO string and `Decimal` → float conversion.

## Tools

The gateway exposes 11 tools:

| Tool                             | Parameters                                                        | Description                          |
|----------------------------------|-------------------------------------------------------------------|--------------------------------------|
| `list_clients`                   | (none)                                                            | List all clients                     |
| `get_client_report_data`         | `client_id`                                                       | Fetch all data for a client report   |
| `save_report`                    | `report_id`, `client_id`, `s3_path`, `generated_date`, `status`   | Save report record                   |
| `save_article`                   | `content_hash`, `url`, `title`, `content`, `summary`, ...         | Save article                         |
| `get_existing_article_hashes`    | (none)                                                            | Get article content hashes for dedup |
| `get_existing_article_urls`      | (none)                                                            | Get article URLs for dedup           |
| `get_recent_articles`            | `hours=48`, `limit=100`                                           | Get recent articles                  |
| `save_theme`                     | `theme_id`, `client_id`, `title`, `sentiment`, `score`, `rank`, . | Save market theme                    |
| `save_theme_article_association` | `theme_id`, `article_hash`, `client_id`                           | Link theme to article                |
| `get_top_holdings_by_aum`        | `client_id`, `limit=5`                                            | Get top holdings by AUM              |
| `get_active_clients`             | (none)                                                            | Get active client IDs                |

## File Structure

```
wealth_management_portal_portfolio_data_server/
├── __init__.py
└── lambda_functions/
    ├── __init__.py
    ├── portfolio_data_gateway.py   # Main gateway — 11 tools, dispatch table, connection pool
    ├── smart_chat_data_access.py   # SQL execution for advisor chat agents
    └── utils.py                    # Shared serialization (date, Decimal)

tests/
├── conftest.py                    # Loads .env, sets AWS_DEFAULT_REGION
├── test_mcp_tools.py             # Gateway tool tests (mock context + lambda_handler)
├── unit/
│   └── test_mcp_tools.py         # Unit tests for _list_clients, _get_client_report_data
└── integration/
    └── test_get_client_report_data.py  # Against real Redshift (requires credentials)
```

## Testing

Unit tests mock the connection factory and repository layer — no database required:

```bash
# Run unit tests (integration tests excluded via pyproject.toml)
uv run pytest tests/
```

Integration tests require IAM credentials and a reachable Redshift Serverless workgroup:

```bash
# Run integration tests only
uv run pytest tests/integration/ -m integration
```

Via Nx:

```bash
# Unit tests (default target)
pnpm nx test wealth_management_portal.portfolio_data_server

# Lint + format
pnpm nx lint wealth_management_portal.portfolio_data_server
```

## Configuration

The Lambda functions read Redshift connection settings from environment variables (inherited from the `portfolio_data_access` library):

| Variable                     | Default                | Description                                    |
|------------------------------|------------------------|------------------------------------------------|
| `REDSHIFT_WORKGROUP`         | `financial-advisor-wg` | Redshift Serverless workgroup name             |
| `REDSHIFT_DATABASE`          | `financial-advisor-db` | Redshift database name                         |
| `AWS_REGION`                 | `us-west-2`           | AWS region                                     |
| `POWERTOOLS_METRICS_NAMESPACE` | `PortfolioDataGateway` | CloudWatch metrics namespace (set in code)   |
| `POWERTOOLS_SERVICE_NAME`    | `PortfolioDataGateway` | Powertools service name (set in code)          |

## Dependencies

Defined in `pyproject.toml`:

- `wealth-management-portal-portfolio-data-access` — shared models and repository layer
- `mcp==1.26.0` — MCP protocol (used by Gateway integration)
- `boto3==1.42.44` — AWS SDK
- `aws-lambda-powertools==3.24.0` — structured logging, tracing, metrics
- `sqlalchemy>=1.4.54` — `QueuePool` for connection pooling

## References

- [AWS Lambda Powertools for Python](https://docs.powertools.aws.dev/lambda/python/latest/) — logging, tracing, metrics decorators
- [Redshift Serverless](https://docs.aws.amazon.com/redshift/latest/mgmt/serverless-whatis.html) — workgroup and namespace concepts
- [SQLAlchemy QueuePool](https://docs.sqlalchemy.org/en/20/core/pooling.html#sqlalchemy.pool.QueuePool) — connection pooling used for Lambda warm invocations
- [Nx Plugin for AWS — Python projects](https://awslabs.github.io/nx-plugin-for-aws/en/guides/python-project/) — build, test, and lint targets used by this package
