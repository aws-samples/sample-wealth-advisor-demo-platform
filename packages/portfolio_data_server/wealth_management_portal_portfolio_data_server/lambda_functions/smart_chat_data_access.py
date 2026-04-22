"""SmartChatDataAccess Lambda — execute_sql tool for advisor chat agents."""

import contextlib
import re

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory

from wealth_management_portal_portfolio_data_server.lambda_functions.utils import serialize_value

logger: Logger = Logger(service="SmartChatDataAccess")
tracer: Tracer = Tracer()

_raw_conn_factory = iam_connection_factory()


@contextlib.contextmanager
def _conn_factory():
    conn = _raw_conn_factory()
    try:
        yield conn
    finally:
        conn.close()


@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext):
    logger.info("Received event", extra={"event": event})

    sql = event.get("sql", "")
    params = event.get("params")

    if not sql:
        return {"error": "No SQL provided"}

    try:
        with _conn_factory() as conn:
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
            rows = [{c: serialize_value(v) for c, v in zip(cols, row, strict=False)} for row in cursor.fetchall()]
            return {"rows": rows}
    except Exception as e:
        logger.exception("execute_sql failed")
        return {"error": str(e)}
