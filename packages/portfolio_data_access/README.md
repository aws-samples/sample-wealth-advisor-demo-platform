# portfolio_data_access

Shared data-access library for the wealth management portal. Provides Pydantic models mirroring Redshift Serverless tables and a repository layer for querying them. Used by multiple consumers — report agents, web crawlers, dashboard APIs, and MCP servers — as the single source of truth for portfolio data operations.

## Architecture

The library has two connection strategies and two repository base classes to match:

```
                        ┌──────────────────────────────┐
                        │         Consumers            │
                        │  (report agent, web crawler, │
                        │   dashboard API, MCP server) │
                        └──────────┬───────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
          ┌─────────────────┐           ┌──────────────────────┐
          │ BaseRepository  │           │ DataApiBaseRepository│
          │ (PEP 249 cursor)│           │ (Redshift Data API)  │
          └────────┬────────┘           └────────────┬─────────┘
                   │                                 │
          ┌────────┴──────────┐           ┌──────────┴───────────┐
          │ engine.py         │           │ data_api_engine.py   │
          │ IAM auth via      │           │ boto3 redshift-data  │
          │ redshift_connector│           │ client               │
          └────────┬──────────┘           └──────────┬───────────┘
                   │                                 │
                   └───────────┬─────────────────────┘
                               ▼
                    ┌──────────────────────┐
                    │  Redshift Serverless │
                    │  financial-advisor-wg│
                    └──────────────────────┘
```

- **BaseRepository** — generic repository using a PEP 249 connection factory (`redshift_connector`). Supports `get()` and `get_one()` with parameterized column filters. Specialized subclasses (e.g. `ThemeRepository`, `ReportRepository`) add writes, joins, and custom queries.
- **DataApiBaseRepository** — base class using the AWS Redshift Data API (`boto3 redshift-data`). Used by dashboard-facing repositories (`ClientRepository`, `HoldingsRepository`, `AUMRepository`, etc.) that run in Lambda where a persistent connection isn't practical.
- **`create_simple_repos()`** — factory function that instantiates `BaseRepository` for all standard tables (clients, accounts, portfolios, holdings, securities, transactions, etc.) in one call.

## File Structure

```
wealth_management_portal_portfolio_data_access/
├── __init__.py                  # Public API — re-exports all models and engine
├── config.py                    # RedshiftConfig (workgroup, database, region, profile)
├── engine.py                    # IAM connection factory (redshift_connector)
├── data_api_engine.py           # Data API connection adapter (boto3 redshift-data)
├── models/
│   ├── __init__.py              # Model re-exports
│   ├── account.py               # Account
│   ├── client.py                # Client, ClientRestriction
│   ├── income_expense.py        # ClientIncomeExpense
│   ├── interaction.py           # Interaction
│   ├── market.py                # Theme, Article, ThemeArticleAssociation
│   ├── performance.py           # PerformanceRecord
│   ├── portfolio.py             # PortfolioRecord, Holding, Security
│   ├── recommended_product.py   # RecommendedProduct
│   ├── report_record.py         # ClientReport
│   └── transaction.py           # Transaction
└── repositories/
    ├── __init__.py              # Repository re-exports + create_simple_repos()
    ├── base.py                  # BaseRepository (generic PEP 249)
    ├── data_api_base_repository.py  # DataApiBaseRepository (Redshift Data API)
    ├── advisor_repository.py    # Top clients by net worth
    ├── allocation_repository.py # Client target allocation
    ├── article_repository.py    # Article CRUD + duplicate detection
    ├── aum_repository.py        # AUM trends + dashboard summary
    ├── client_details_repository.py # Client detail lookup
    ├── client_report_repository.py  # Client report data from Redshift views
    ├── client_repository.py     # Client list (paginated)
    ├── client_segment_repository.py # Segment aggregation
    ├── holdings_repository.py   # Client holdings (paginated)
    ├── interaction_repository.py    # Recent interactions (ordered)
    ├── performance_repository.py    # Date-range performance queries
    ├── portfolio_repository.py  # Holdings enriched with security details
    ├── report_repository.py     # Report CRUD + status tracking
    ├── theme_repository.py      # Theme + ThemeArticle save/query
    └── transactions_repository.py   # Client transactions (paginated)

tests/
├── conftest.py                  # Loads .env, sets AWS_DEFAULT_REGION
├── test_article_repository.py   # ArticleRepository unit tests
├── test_theme_repository.py     # ThemeRepository unit tests
├── unit/
│   ├── test_models.py           # Model import smoke test
│   └── test_repositories.py    # Repository unit tests (mock PEP 249 connection)
└── integration/
    ├── test_engine_smoke.py     # IAM connection smoke test
    └── test_repositories.py     # All repositories against real Redshift
```

## Testing

Unit tests use a mock PEP 249 connection — no database required:

```bash
# Run unit tests (default — integration tests are excluded via pyproject.toml)
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
pnpm nx test wealth_management_portal.portfolio_data_access

# Lint + format
pnpm nx lint wealth_management_portal.portfolio_data_access
```

## Configuration

Set via environment variables or `.env` file at the package root:

| Variable | Default | Description |
|---|---|---|
| `REDSHIFT_WORKGROUP` | `financial-advisor-wg` | Redshift Serverless workgroup name |
| `REDSHIFT_DATABASE` | `financial-advisor-db` | Redshift database name |
| `AWS_REGION` | `us-west-2` | AWS region |
| `AWS_PROFILE` | (none) | AWS profile for local dev |
| `USE_DEFAULT_AWS_CREDENTIALS` | `false` | Skip profile, use default credential chain |
| `REDSHIFT_HOST` | (none) | Set for tunnel mode (SSM port forwarding) |
| `REDSHIFT_PORT` | `5439` | Redshift port (tunnel mode) |
| `AWS_ACCOUNT_ID` | (required) | AWS account ID for standard serverless mode |

## Dependencies

Defined in `pyproject.toml`:

- `pydantic>=2.12.5` — data models and validation
- `redshift-connector>=2.1.0` — IAM-authenticated Redshift connections (PEP 249)
- `boto3==1.42.44` — Redshift Data API and credential retrieval

Dev/test dependencies are managed at the workspace root via `uv`.

## References

- [Pydantic v2 docs](https://docs.pydantic.dev/latest/) — model validation and serialization
- [redshift_connector](https://github.com/aws/amazon-redshift-python-driver) — IAM-authenticated Python driver for Redshift
- [Redshift Data API](https://docs.aws.amazon.com/redshift/latest/mgmt/data-api.html) — stateless HTTP-based query execution
- [Redshift Serverless](https://docs.aws.amazon.com/redshift/latest/mgmt/serverless-whatis.html) — workgroup and namespace concepts
- [Nx Plugin for AWS — Python projects](https://awslabs.github.io/nx-plugin-for-aws/en/guides/python-project/) — build, test, and lint targets used by this package
