"""Shared text-to-SQL tool — LLM generates SQL, this tool executes it."""

import json

from strands import tool

from .redshift import execute_query


@tool
def run_sql(sql: str) -> str:
    """Execute a read-only SQL query against the Redshift data warehouse.

    Args:
        sql: A SELECT query to run. Must be read-only (no INSERT/UPDATE/DELETE).

    Returns:
        JSON array of result rows.
    """
    blocked = sql.strip().upper()
    if not blocked.startswith("SELECT") and not blocked.startswith("WITH"):
        return json.dumps({"error": "Only SELECT queries are allowed."})

    # Enforce LIMIT to prevent token overflow
    if "LIMIT" not in blocked:
        sql = sql.rstrip().rstrip(";") + " LIMIT 50"

    try:
        rows = execute_query(sql)
        return json.dumps(rows, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})
