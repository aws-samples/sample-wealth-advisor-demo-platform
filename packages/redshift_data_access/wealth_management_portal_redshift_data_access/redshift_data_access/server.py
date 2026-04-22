"""RedshiftDataAccess MCP server — single execute_sql tool for read-only queries."""

import logging
import os
import re
from datetime import date
from decimal import Decimal

from mcp.server.fastmcp import FastMCP
from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory

mcp = FastMCP(
    name="RedshiftDataAccess",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
    stateless_http=True,
)

_conn_factory = iam_connection_factory()
logger = logging.getLogger(__name__)


def _serialize(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


@mcp.tool()
def execute_sql(sql: str, params: list[str] | None = None) -> dict:
    """Execute a read-only SQL query against Redshift and return rows as list of dicts.

    Args:
        sql: SQL SELECT query. Use :p0, :p1 etc. for parameter placeholders.
        params: Optional list of string parameter values matching :p0, :p1 order.

    Returns:
        Dict with 'rows' list of dicts, or 'error' string.
    """
    try:
        conn = _conn_factory()
        try:
            cursor = conn.cursor()
            converted = sql
            ordered_params = []
            if params:

                def replacer(m):
                    idx = int(m.group(1))
                    ordered_params.append(params[idx] if idx < len(params) else None)
                    return "%s"

                converted = re.sub(r":p(\d+)", replacer, sql)
            cursor.execute(converted, ordered_params or None)
            cols = [d[0] for d in cursor.description]
            rows = [{c: _serialize(v) for c, v in zip(cols, row)} for row in cursor.fetchall()]
            return {"rows": rows}
        finally:
            conn.close()
    except Exception as e:
        logger.exception("execute_sql failed")
        return {"error": str(e)}
