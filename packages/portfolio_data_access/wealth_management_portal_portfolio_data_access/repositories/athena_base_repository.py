"""Base repository for Athena query access to S3 Tables (Iceberg)."""

import os
import re
import time

import boto3

from ..config import config


class AthenaBaseRepository:
    """Base class for repositories using the Athena query API against S3 Tables."""

    def __init__(
        self,
        workgroup: str | None = None,
        output_location: str | None = None,
        catalog: str | None = None,
        database: str | None = None,
        region: str | None = None,
        profile_name: str | None = None,
    ) -> None:
        self.workgroup = workgroup or config.athena_workgroup
        self.output_location = output_location or config.athena_output_location
        self.catalog = catalog or config.athena_catalog
        self.database = database or config.athena_database
        region = region or config.region
        profile_name = profile_name if profile_name is not None else config.get_profile_name()

        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region)
        else:
            session = boto3.Session(region_name=region)

        self.client = session.client("athena")

    def _resolve_sql(self, sql: str, parameters: list[dict] | None = None) -> str:
        """Replace named :param placeholders and qualify bare table names."""
        if self.catalog and self.database:
            sql = self._qualify_tables(sql)
        if not parameters:
            return sql
        for param in parameters:
            name = param["name"]
            value = param["value"]
            # Allowlist must stay in sync with common_market_events/redshift.py's
            # sanitizer. Keep ':' '/' '+' so ISO timestamps (e.g. '2026-08-05
            # 22:34:39') are not corrupted. TODO: extract a single shared helper.
            safe_value = re.sub(r"[^\w\s\-._:/+]", "", value)
            if safe_value.isdigit():
                sql = sql.replace(f":{name}", safe_value)
            else:
                sql = sql.replace(f":{name}", f"'{safe_value}'")
        return sql

    def _qualify_tables(self, sql: str) -> str:
        """Prefix bare table names with catalog.database to avoid QueryExecutionContext issues."""
        table_names = [
            "accounts",
            "advisors",
            "articles",
            "client_income_expense",
            "client_investment_restrictions",
            "client_reports",
            "clients",
            "compliance",
            "crawl_log",
            "documents",
            "fees",
            "goals",
            "holdings",
            "interactions",
            "market_data",
            "performance",
            "portfolio_config",
            "portfolios",
            "recommended_products",
            "research",
            "securities",
            "theme_article_associations",
            "themes",
            "transactions",
        ]
        prefix = f'"{self.catalog}"."{self.database}".'
        for table in table_names:
            sql = re.sub(
                rf'(?<![.\w"])(\b{table}\b)(?![.\w])',
                prefix + f'"{table}"',
                sql,
            )
        return sql

    def _execute_parameterized(
        self,
        sql: str,
        values: list,
        poll_interval: float = 0.5,
        max_attempts: int = 120,
    ) -> list[dict]:
        """Execute a positional-placeholder (``?``) statement using Athena's
        ExecutionParameters for safe server-side binding — NO string interpolation.

        Use this for writes/reads whose values may contain quotes, commas or
        newlines (article/theme text), where the string-interpolation path would
        corrupt or break the query. Note: Athena rejects empty-string parameters,
        so callers should map NULL/empty to a sentinel and use NULLIF in the SQL.
        Returns rows for a SELECT, otherwise an empty list.
        """
        if self.catalog and self.database:
            sql = self._qualify_tables(sql)
        start_kwargs: dict = {
            "QueryString": sql,
            "WorkGroup": self.workgroup,
            "ExecutionParameters": [str(v) for v in values],
        }
        if self.output_location:
            start_kwargs["ResultConfiguration"] = {"OutputLocation": self.output_location}

        query_execution_id = self.client.start_query_execution(**start_kwargs)["QueryExecutionId"]

        for _attempt in range(max_attempts):
            status = self.client.get_query_execution(QueryExecutionId=query_execution_id)["QueryExecution"]["Status"]
            state = status["State"]
            if state == "SUCCEEDED":
                break
            if state == "FAILED":
                raise Exception(f"Athena query failed: {status.get('StateChangeReason', 'Unknown error')}")
            if state == "CANCELLED":
                raise Exception("Athena query was cancelled")
            time.sleep(poll_interval)
        else:
            raise Exception("Athena query timed out")

        result_rows = (
            self.client.get_query_results(QueryExecutionId=query_execution_id).get("ResultSet", {}).get("Rows", [])
        )
        if not result_rows:
            return []
        columns = [col.get("VarCharValue", "") for col in result_rows[0]["Data"]]
        return [
            {col: cell.get("VarCharValue") for col, cell in zip(columns, record["Data"], strict=True)}
            for record in result_rows[1:]
        ]

    def _execute_and_wait(
        self,
        sql: str,
        parameters: list[dict] | None = None,
        poll_interval: float = 0.5,
        max_attempts: int = 120,
    ) -> list[dict]:
        """Execute SQL via Athena, wait for completion, and return rows.

        Args:
            sql: The SQL statement to execute.
            parameters: Optional named parameters (same format as Redshift Data API for compatibility).
            poll_interval: Seconds between status polls.
            max_attempts: Maximum number of poll attempts before raising a timeout error.

        Returns:
            Query results as a list of dicts keyed by column name.
        """
        resolved_sql = self._resolve_sql(sql, parameters)

        start_kwargs: dict = {
            "QueryString": resolved_sql,
            "WorkGroup": self.workgroup,
        }
        if self.output_location:
            start_kwargs["ResultConfiguration"] = {"OutputLocation": self.output_location}
        # Athena result reuse (engine v3): identical read queries within the
        # window return cached results in ~ms instead of re-scanning S3.
        # Deterministic API reads (dashboards, lists, client detail) benefit
        # most. ATHENA_RESULT_REUSE_MINUTES=0 disables it.
        try:
            _reuse_min = int(os.environ.get("ATHENA_RESULT_REUSE_MINUTES", "10"))
        except ValueError:
            _reuse_min = 10
        if _reuse_min > 0:
            start_kwargs["ResultReuseConfiguration"] = {
                "ResultReuseByAgeConfiguration": {
                    "Enabled": True,
                    "MaxAgeInMinutes": _reuse_min,
                }
            }

        response = self.client.start_query_execution(**start_kwargs)
        query_execution_id = response["QueryExecutionId"]

        for _attempt in range(max_attempts):
            status_response = self.client.get_query_execution(QueryExecutionId=query_execution_id)
            state = status_response["QueryExecution"]["Status"]["State"]
            if state == "SUCCEEDED":
                break
            if state == "FAILED":
                reason = status_response["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
                raise Exception(f"Athena query failed: {reason}")
            if state == "CANCELLED":
                raise Exception("Athena query was cancelled")
            time.sleep(poll_interval)
        else:
            raise Exception("Athena query timed out")

        result = self.client.get_query_results(QueryExecutionId=query_execution_id)
        result_rows = result.get("ResultSet", {}).get("Rows", [])

        if not result_rows:
            return []

        columns = [col.get("VarCharValue", "") for col in result_rows[0]["Data"]]

        rows = []
        for record in result_rows[1:]:
            row = {}
            for col_name, cell in zip(columns, record["Data"], strict=True):
                value = cell.get("VarCharValue")
                row[col_name] = value
            rows.append(row)

        return rows
