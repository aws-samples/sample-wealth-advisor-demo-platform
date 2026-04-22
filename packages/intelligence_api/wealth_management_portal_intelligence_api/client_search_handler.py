"""Natural language client search using strands-agents + Redshift."""

import json
import logging
import re

import boto3
from botocore.config import Config
from pydantic import BaseModel
from wealth_management_portal_portfolio_data_access.config import config
from wealth_management_portal_portfolio_data_access.data_api_engine import DataApiConnection

logger = logging.getLogger(__name__)

CLIENT_LIST_VIEW = "client_search"


class UnsafeSQLError(Exception):
    """Raised when generated SQL fails safety validation."""


_FORBIDDEN_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|COPY|UNLOAD|CALL)\b",
    re.IGNORECASE,
)

_ALLOWED_SQL_PATTERN = re.compile(
    r"^\s*SELECT\s+.+\s+FROM\s+client_search\b",
    re.IGNORECASE | re.DOTALL,
)


def validate_generated_sql(sql: str) -> str:
    """Validate that LLM-generated SQL is a safe, read-only query against client_search.

    Raises UnsafeSQLError if the SQL is rejected.
    """
    stripped = sql.strip().rstrip(";")

    if _FORBIDDEN_PATTERN.search(stripped):
        raise UnsafeSQLError(f"SQL contains forbidden keywords: {stripped[:200]}")

    if not _ALLOWED_SQL_PATTERN.match(stripped):
        raise UnsafeSQLError("SQL must be a SELECT query against the client_search view")

    if ";" in stripped:
        raise UnsafeSQLError("SQL must not contain multiple statements")

    from_join_refs = re.findall(r"\b(?:FROM|JOIN)\s+(\w+)", stripped, re.IGNORECASE)
    for table_ref in from_join_refs:
        if table_ref.lower() != CLIENT_LIST_VIEW:
            raise UnsafeSQLError(f"SQL references unauthorized table: {table_ref}")

    return stripped


VIEW_SCHEMA = """  client_id VARCHAR(10),
  client_first_name VARCHAR(100),
  client_last_name VARCHAR(100),
  client_name TEXT,
  email VARCHAR(255),
  phone VARCHAR(20),
  address VARCHAR(255),
  city VARCHAR(100),
  state VARCHAR(2),
  zip VARCHAR(20),
  date_of_birth DATE,
  risk_tolerance VARCHAR(30),
  investment_objectives VARCHAR(100),
  segment VARCHAR(30),
  status VARCHAR(20),
  client_since DATE,
  sophistication VARCHAR(30),
  qualified_investor BOOLEAN,
  service_model VARCHAR(30),
  advisor_id VARCHAR(10),
  advisor_name TEXT,
  aum NUMERIC(38,2),
  net_worth NUMERIC(38,2),
  ytd_performance NUMERIC(38,4),
  interaction_sentiment VARCHAR(20),
  report_id VARCHAR(14),
  s3_path VARCHAR(500),
  generated_date TIMESTAMP,
  income_expense_as_of_date DATE,
  monthly_income NUMERIC(18,2),
  monthly_expenses NUMERIC(18,2),
  monthly_net NUMERIC(20,2),
  sustainability_years NUMERIC(10,2),
  compliance_id VARCHAR(10),
  kyc_status VARCHAR(20),
  kyc_date DATE,
  aml_status VARCHAR(20),
  aml_date DATE,
  suitability_status VARCHAR(20),
  suitability_date DATE,
  next_review_date DATE,
  restriction_count BIGINT,
  restrictions_list VARCHAR(16000000),
  total_goals BIGINT,
  goals_total_target_amount NUMERIC(38,2),
  goals_total_current_value NUMERIC(38,2),
  goals_on_track BIGINT,
  goals_behind BIGINT,
  theme_count BIGINT,
  recommended_tickers VARCHAR(1000),
  portfolio_config_generated_at TIMESTAMP"""

SYSTEM_PROMPT = f"""You are an SQL query generator for a Redshift '{CLIENT_LIST_VIEW}' view.
Convert natural language to SELECT queries. Return ONLY the SQL, nothing else.

Table: {CLIENT_LIST_VIEW}
Columns:
{VIEW_SCHEMA}

Rules:
- Always include LIMIT 100 unless user specifies otherwise
- Use ILIKE '%term%' for string matching
- "unhappy"/"hates me" → interaction_sentiment = 'Negative'
- "happy" → interaction_sentiment = 'Positive'
- "engaged" → interaction_sentiment IN ('Positive', 'Neutral')
- "disengaged" → interaction_sentiment = 'Negative'
- Name searches → client_first_name/client_last_name ILIKE
- AUM → aum column; net worth → net_worth column
- Always return valid Redshift SQL"""


class ClientSearchRequest(BaseModel):
    query: str


class ClientSearchResponse(BaseModel):
    success: bool
    data: list[dict] = []
    columns: list[str] = []
    generated_sql: str = ""
    error: str = ""


def _generate_sql(nl_query: str) -> str:
    """Use Bedrock to convert natural language to SQL."""
    bedrock = boto3.client(
        "bedrock-runtime", config=Config(region_name="us-east-1", retries={"max_attempts": 3, "mode": "adaptive"})
    )
    response = bedrock.invoke_model(
        modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "temperature": 0,
                "messages": [{"role": "user", "content": f"{SYSTEM_PROMPT}\n\nUser query: {nl_query}"}],
            }
        ),
    )
    text = json.loads(response["body"].read())["content"][0]["text"].strip()
    # Strip markdown fences
    text = re.sub(r"```sql\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*", "", text)
    match = re.search(r"(SELECT\s+.+)", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip().rstrip(";") if match else f"SELECT * FROM {CLIENT_LIST_VIEW} LIMIT 100"


def search_clients_nl(query: str) -> ClientSearchResponse:
    """Search clients using natural language via LLM-generated SQL."""
    try:
        sql = _generate_sql(query)
        logger.info(f"Generated SQL: {sql}")

        safe_sql = validate_generated_sql(sql)

        conn = DataApiConnection(workgroup=config.workgroup, database=config.database, region=config.region)
        cursor = conn.cursor()
        cursor.execute(safe_sql)

        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        data = [
            {columns[i]: (str(row[i]) if row[i] is not None else None) for i in range(len(columns))}
            for row in cursor.fetchall()
        ]

        return ClientSearchResponse(success=True, data=data, columns=columns, generated_sql=safe_sql)
    except UnsafeSQLError as e:
        logger.warning("Blocked unsafe SQL: %s", e)
        return ClientSearchResponse(success=False, error="Generated query was rejected by safety validation.")
    except Exception as e:
        logger.error(f"Client search error: {e}")
        return ClientSearchResponse(success=False, error=str(e))
