# Client Search — Natural Language to SQL

Intelligent client search that converts natural language queries into SQL, enabling financial advisors to find clients using natual language questions. questions instead of writing database queries.

## Overview

Client Search uses a TEXT2SQL approach: an LLM interprets the advisor's natural language question, generates a safe SQL query against a Redshift Serverless view (`client_search`), executes it, and returns structured results to the UI.

**Example queries:**
- "Clients in New York with AUM over 5M"
- "Show me UHNW clients with aggressive risk tolerance"
- "Clients who are unhappy or disengaged"
- "Find customers interested in Retirement located in NYC"

## Technology Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.12 | Runtime |
| FastAPI | 0.128.5 | HTTP server for the agent |
| Strands Agents | 1.25.0 | LLM agent framework for NL-to-SQL generation |
| Pydantic | ≥2.12.5 | Request/response validation |
| boto3 | 1.42.44 | AWS SDK (Bedrock, AgentCore, Redshift Data API) |
| UV | — | Python package manager |

## AWS Services

| Service | Role |
|---|---|
| Amazon Bedrock |  NL-to-SQL generation |
| Amazon Bedrock AgentCore | Hosts the client search agent as an HTTP runtime (Docker, ARM64) |
| Amazon Redshift Serverless | Data warehouse — queries the `client_search` view via Data API |
| Amazon API Gateway | REST API with Cognito authorizer exposing `POST /clients/search` |
| Amazon Cognito | User authentication and API authorization |
| AWS Lambda | Runs the Core API (Python 3.12, ARM64) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              React UI                                   │
│  ClientSearch.tsx — search box + sortable client table                  │
│  Routes: /clients (list view) and /clients (graph view toggle)          │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ POST /clients/search
                               ▼
                  ┌──────────────────────────┐
                  │        Core API          │
                  │    (packages/api)        │
                  │   Lambda + API Gateway   │
                  └────────────┬─────────────┘
                               │
                  ┌────────────▼─────────────┐
                  │    Schema Discovery      │
                  │    SELECT * FROM         │
                  │    client_search LIMIT 0 │
                  └────────────┬─────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        NL-to-SQL Generation                              │
│                                                                          │
│  ┌─ Deployed ──────────────────────┐  ┌─ Local Dev ───────────────────┐  │
│  │  AgentCore Runtime              │  │  Direct Bedrock InvokeModel   │  │
│  │  (client_search_agent)          │  │                               │  │
│  │  Strands Agent + FastAPI        │  │                               │  │
│  │  POST /invocations              │  │                               │  │
│  └─────────────────────────────────┘  └───────────────────────────────┘  │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │ Generated SQL
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        SQL Safety Validation                             │
│  • Must be SELECT only (blocks INSERT/UPDATE/DELETE/DROP/ALTER/etc.)     │
│  • Must query only the client_search view                                │
│  • No semicolons (blocks multi-statement injection)                      │
│  • No subqueries referencing other tables                                │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │ Validated SQL
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     Amazon Redshift Serverless                           │
│  Executes query against public.client_search view via Data API           │
│  Returns structured rows → mapped to JSON response                       │
└──────────────────────────────────────────────────────────────────────────┘
```

## End-to-End Flow

### 1. User Input
The advisor types a natural language query in the UI search box on the `/clients` page (e.g., "Show me UHNW clients in California with AUM over 10M").

### 2. API Request
The React `ClientSearch` component sends a `POST` request to the Core API at `/clients/search` with the query string.

### 3. Schema Discovery
The handler dynamically discovers the `client_search` view schema by executing `SELECT * FROM client_search LIMIT 0` against Redshift. Column names and types are cached in-process for subsequent requests.

### 4. NL-to-SQL Generation
The natural language query and table schema are sent to an LLM for SQL generation:

- **Deployed (production):** The Core API invokes the Client Search Agent hosted on Bedrock AgentCore via `invoke_agent_runtime`. The agent is a Strands Agent running inside a Docker container (ARM64) with a FastAPI server. It receives the query + schema at `POST /invocations` and returns the generated SQL.
- **Local development:** The handler calls Bedrock `InvokeModel` directly with Claude Sonnet 3.5 v2, bypassing the agent server.

The LLM system prompt instructs the model to:
- Generate valid Redshift SQL syntax only
- Use `ILIKE '%term%'` for case-insensitive string matching
- Map name searches to `client_first_name` / `client_last_name`
- Map sentiment language ("unhappy", "hates me" → `interaction_sentiment = 'Negative'`)
- Always include `LIMIT 100` unless specified otherwise
- Return only the SQL query with no explanation

### 5. SQL Safety Validation
Before execution, the generated SQL passes through a multi-layer validation:

1. **Forbidden keyword check** — rejects any DDL/DML keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`, `REVOKE`, `EXEC`, `COPY`, `UNLOAD`, `CALL`)
2. **Allowed pattern check** — SQL must be a `SELECT ... FROM client_search` query
3. **Multi-statement check** — rejects semicolons to prevent SQL injection
4. **Table reference check** — all `FROM` and `JOIN` references must be `client_search` only

If validation fails, the query is rejected with a safety error before reaching the database.

### 6. Query Execution
The validated SQL is executed against Amazon Redshift Serverless via the Data API (`DataApiConnection`). Results are returned as a list of dictionaries with column names as keys.

### 7. Response
The API returns a `ClientSearchResponse` containing:
- `success`: boolean
- `data`: array of client records
- `columns`: column names
- `generated_sql`: the SQL that was executed (for transparency)
- `error`: error message if failed

### 8. UI Rendering
The React component maps the response data into a sortable table displaying: Customer Name, Segment, AUM, Net Worth, YTD Performance, Goal Progress, Risk Tolerance, Client Since, Interaction Sentiment, Client Report link, and Next Best Actions.

## Project Structure

```
packages/client_search/
├── wealth_management_portal_client_search/
│   ├── __init__.py
│   └── client_search_agent/
│       ├── __init__.py          # FastAPI app setup (CORS, error handling, OpenAPI)
│       ├── agent.py             # Strands Agent with NL-to-SQL system prompt
│       ├── main.py              # POST /invocations endpoint + SQL extraction
│       └── Dockerfile           # ARM64 container for AgentCore deployment
├── tests/
│   ├── conftest.py
│   └── test_agent.py
├── pyproject.toml
└── README.md
```
