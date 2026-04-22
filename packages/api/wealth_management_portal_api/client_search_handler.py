"""Handler for natural language client search endpoint.

Uses AgentCore Strands agent for NL-to-SQL generation,
then executes the SQL against Redshift via Data API.
"""

import json
import logging
import os
import re
import uuid

import boto3
import botocore.config
from pydantic import BaseModel
from wealth_management_portal_portfolio_data_access.config import config
from wealth_management_portal_portfolio_data_access.data_api_engine import (
    DataApiConnection,
)

logger = logging.getLogger(__name__)

CLIENT_LIST_VIEW = "client_search"

# Global AgentCore client for reuse across invocations
_agentcore = None


def _get_agentcore_client():
    global _agentcore
    if _agentcore is None:
        _agentcore = boto3.client(
            "bedrock-agentcore",
            config=botocore.config.Config(read_timeout=60),
        )
    return _agentcore


_VIEW_SCHEMA: str | None = None


# Mapping from psycopg2/redshift-connector type codes to readable SQL type names
_TYPE_CODE_MAP = {
    16: "BOOLEAN",
    17: "BYTEA",
    20: "BIGINT",
    21: "SMALLINT",
    23: "INTEGER",
    25: "TEXT",
    700: "REAL",
    701: "DOUBLE PRECISION",
    1043: "VARCHAR",
    1082: "DATE",
    1083: "TIME",
    1114: "TIMESTAMP",
    1184: "TIMESTAMPTZ",
    1700: "NUMERIC",
    2950: "UUID",
}


def _resolve_type(type_code) -> str:
    """Convert a DB-API type code to a human-readable SQL type name."""
    if isinstance(type_code, int):
        return _TYPE_CODE_MAP.get(type_code, "VARCHAR")
    # Already a string (some drivers return type names directly)
    return str(type_code) if type_code else "VARCHAR"


def _get_view_schema() -> str:
    global _VIEW_SCHEMA
    if _VIEW_SCHEMA is None:
        conn = DataApiConnection(
            workgroup=config.workgroup,
            database=config.database,
            region=config.region,
        )
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT * FROM {CLIENT_LIST_VIEW} LIMIT 0;")
            columns = cursor.description or []
            lines = [f"  {col[0]} {_resolve_type(col[1]) if len(col) > 1 else 'VARCHAR'}" for col in columns]
            _VIEW_SCHEMA = ",\n".join(lines)
            logger.info("Loaded schema with %d columns", len(columns))
        except Exception as e:
            logger.warning("Could not load schema: %s", e)
            _VIEW_SCHEMA = "  -- Schema could not be loaded."
    return _VIEW_SCHEMA


class ClientSearchRequest(BaseModel):
    query: str


class ClientSearchResponse(BaseModel):
    success: bool
    data: list[dict] = []
    columns: list[str] = []
    generated_sql: str = ""
    error: str = ""


class UnsafeSQLError(Exception):
    """Raised when generated SQL fails safety validation."""


# Forbidden SQL keywords that indicate DDL/DML/dangerous operations
_FORBIDDEN_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|COPY|UNLOAD|CALL)\b",
    re.IGNORECASE,
)

# Generated SQL must be a SELECT from the client_search view only
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

    # Block semicolons (multi-statement injection)
    if ";" in stripped:
        raise UnsafeSQLError("SQL must not contain multiple statements")

    # Block subqueries referencing other tables
    # Count FROM/JOIN occurrences — all must reference client_search
    from_join_refs = re.findall(r"\b(?:FROM|JOIN)\s+(\w+)", stripped, re.IGNORECASE)
    for table_ref in from_join_refs:
        if table_ref.lower() != CLIENT_LIST_VIEW:
            raise UnsafeSQLError(f"SQL references unauthorized table: {table_ref}")

    return stripped


def execute_redshift_query(sql_query: str) -> dict:
    """Execute validated SQL on Redshift Serverless via Data API."""
    try:
        safe_sql = validate_generated_sql(sql_query)
        conn = DataApiConnection(workgroup=config.workgroup, database=config.database, region=config.region)
        cursor = conn.cursor()
        cursor.execute(safe_sql)

        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        data = []
        for row in cursor.fetchall():
            record = {}
            for i, col_name in enumerate(columns):
                record[col_name] = str(row[i]) if row[i] is not None else None
            data.append(record)

        return {"success": True, "data": data, "columns": columns}
    except UnsafeSQLError as e:
        logger.warning("Blocked unsafe SQL: %s", e)
        return {
            "success": False,
            "error": "Generated query was rejected by safety validation.",
        }
    except Exception as e:
        logger.error("Error executing query: %s", e)
        return {"success": False, "error": str(e)}


def _generate_sql_via_bedrock(nl_query: str) -> str:
    """Use Bedrock Claude to convert natural language to SQL."""
    schema = _get_view_schema()
    system_prompt = f"""You are an SQL query generator for a Redshift '{CLIENT_LIST_VIEW}' table.
Convert natural language to SELECT queries. Return ONLY the SQL, nothing else.

Table: {CLIENT_LIST_VIEW}
Columns:
{schema}

Rules:
- Always include LIMIT 100 unless user specifies otherwise
- Use ILIKE '%term%' for string matching
- Name searches -> client_first_name/client_last_name ILIKE
- AUM column is 'aum' (numeric, in dollars)
- "more than 1M" -> aum > 1000000
- Always return valid Redshift SQL"""

    bedrock = boto3.client(
        "bedrock-runtime",
        config=botocore.config.Config(
            region_name="us-east-1",
            retries={"max_attempts": 3, "mode": "adaptive"},
        ),
    )
    response = bedrock.invoke_model(
        modelId=os.environ.get("CLIENT_SEARCH_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "temperature": 0,
                "messages": [
                    {
                        "role": "user",
                        "content": f"{system_prompt}\n\nUser query: {nl_query}",
                    }
                ],
            }
        ),
    )
    text = json.loads(response["body"].read())["content"][0]["text"].strip()
    text = re.sub(r"```sql\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*", "", text)
    match = re.search(r"(SELECT\s+.+)", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip().rstrip(";") if match else f"SELECT * FROM {CLIENT_LIST_VIEW} LIMIT 100"


def search_clients_nl(query: str) -> ClientSearchResponse:
    """Search clients using NL query via AgentCore Strands agent."""
    try:
        agent_arn = os.environ.get("CLIENT_SEARCH_AGENT_ARN", "")
        schema = _get_view_schema()
        payload = {"query": query, "table_schema": schema}

        if agent_arn:
            # Deployed: call AgentCore
            session_id = f"search-{uuid.uuid4().hex}"
            logger.info("Invoking client search agent via AgentCore")
            client = _get_agentcore_client()
            response = client.invoke_agent_runtime(
                agentRuntimeArn=agent_arn,
                runtimeSessionId=session_id,
                payload=json.dumps(payload),
            )
            result = json.loads(response["response"].read())
        else:
            # Local dev: use Bedrock directly for text-to-SQL
            logger.info("Generating SQL via Bedrock for query: %s", query)
            sql = _generate_sql_via_bedrock(query)
            result = {"sql": sql}

        sql = result.get("sql", f"SELECT * FROM {CLIENT_LIST_VIEW} LIMIT 100")
        logger.info("Generated SQL: %s", sql)

        data = execute_redshift_query(sql)
        return ClientSearchResponse(
            success=data.get("success", False),
            data=data.get("data", []),
            columns=data.get("columns", []),
            generated_sql=sql,
            error=data.get("error", ""),
        )
    except Exception as e:
        logger.error("Client search error: %s", e)
        return ClientSearchResponse(success=False, error=str(e))
