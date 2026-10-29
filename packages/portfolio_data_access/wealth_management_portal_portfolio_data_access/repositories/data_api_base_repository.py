"""Base repository that auto-selects Athena or Redshift based on DATA_ENGINE config."""

import time

import boto3

from ..config import config


def _create_redshift_base(workgroup, database, region, profile_name):
    """Create a Redshift Data API-based implementation."""

    class _RedshiftBase:
        def __init__(self):
            self.workgroup = workgroup or config.workgroup
            self.database = database or config.database
            _region = region or config.region
            _profile = profile_name if profile_name is not None else config.get_profile_name()

            if _profile:
                session = boto3.Session(profile_name=_profile, region_name=_region)
            else:
                session = boto3.Session(region_name=_region)

            self.client = session.client("redshift-data")

        def _execute_and_wait(self, sql, parameters=None, poll_interval=0.5, max_attempts=60):
            kwargs = {"WorkgroupName": self.workgroup, "Database": self.database, "Sql": sql}
            if parameters:
                kwargs["Parameters"] = parameters
            statement_id = self.client.execute_statement(**kwargs)["Id"]

            for _ in range(max_attempts):
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

    return _RedshiftBase()


class DataApiBaseRepository:
    """Base class that delegates to Athena or Redshift depending on DATA_ENGINE env var."""

    def __init__(
        self,
        workgroup: str | None = None,
        database: str | None = None,
        region: str | None = None,
        profile_name: str | None = None,
    ) -> None:
        if config.engine == "athena":
            from .athena_base_repository import AthenaBaseRepository

            self._delegate = AthenaBaseRepository(
                region=region,
                profile_name=profile_name,
            )
        else:
            self._delegate = _create_redshift_base(workgroup, database, region, profile_name)

    def _execute_and_wait(
        self,
        sql: str,
        parameters: list[dict] | None = None,
        poll_interval: float = 0.5,
        max_attempts: int = 60,
    ) -> list[dict]:
        return self._delegate._execute_and_wait(sql, parameters, poll_interval, max_attempts)

    def _execute_parameterized(
        self,
        sql: str,
        values: list,
        poll_interval: float = 0.5,
        max_attempts: int = 120,
    ) -> list[dict]:
        """Safe positional-parameter (?) execution — Athena engine only."""
        return self._delegate._execute_parameterized(sql, values, poll_interval, max_attempts)
