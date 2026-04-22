"""Base repository for Redshift Data API access."""

import time

import boto3

from ..config import config


class DataApiBaseRepository:
    """Base class for repositories using the Redshift Data API."""

    def __init__(
        self,
        workgroup: str | None = None,
        database: str | None = None,
        region: str | None = None,
        profile_name: str | None = None,
    ) -> None:
        self.workgroup = workgroup or config.workgroup
        self.database = database or config.database
        region = region or config.region
        profile_name = profile_name if profile_name is not None else config.get_profile_name()

        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region)
        else:
            session = boto3.Session(region_name=region)

        self.client = session.client("redshift-data")

    def _execute_statement(self, sql: str, parameters: list[dict] | None = None) -> str:
        """Submit a SQL statement and return its execution ID.

        Args:
            sql: The SQL statement to execute.
            parameters: Optional list of SqlParameters dicts for parameterised queries.

        Returns:
            The statement execution ID.
        """
        kwargs: dict = {"WorkgroupName": self.workgroup, "Database": self.database, "Sql": sql}
        if parameters:
            kwargs["Parameters"] = parameters
        return self.client.execute_statement(**kwargs)["Id"]

    def _execute_and_wait(
        self,
        sql: str,
        parameters: list[dict] | None = None,
        poll_interval: float = 0.5,
        max_attempts: int = 60,
    ) -> list[dict]:
        """Execute SQL via the Data API, wait for completion, and return rows.

        Args:
            sql: The SQL statement to execute.
            parameters: Optional SqlParameters for parameterised queries (prevents SQL injection).
            poll_interval: Seconds between status polls.
            max_attempts: Maximum number of poll attempts before raising a timeout error.

        Returns:
            Query results as a list of dicts keyed by column name.

        Raises:
            Exception: On query failure, abort, or timeout.
        """
        statement_id = self._execute_statement(sql, parameters)

        for _attempt in range(max_attempts):
            status_response = self.client.describe_statement(Id=statement_id)
            status = status_response["Status"]
            if status == "FINISHED":
                break
            if status == "FAILED":
                raise Exception(f"Query failed: {status_response.get('Error', 'Unknown error')}")
            if status == "ABORTED":
                raise Exception("Query was aborted")
            time.sleep(poll_interval)
        else:
            raise Exception("Query timed out")

        result = self.client.get_statement_result(Id=statement_id)
        columns = [col["name"] for col in result["ColumnMetadata"]]

        rows = []
        for record in result.get("Records", []):
            row = {}
            for col_name, value in zip(columns, record, strict=True):
                if "stringValue" in value:
                    row[col_name] = value["stringValue"]
                elif "longValue" in value:
                    row[col_name] = value["longValue"]
                elif "doubleValue" in value:
                    row[col_name] = value["doubleValue"]
                elif value.get("isNull"):
                    row[col_name] = None
                else:
                    row[col_name] = None
            rows.append(row)

        return rows
