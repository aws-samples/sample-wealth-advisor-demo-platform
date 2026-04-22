# AWS Redshift Data API connection adapter compatible with redshift_connector cursor interface
import time

import boto3

from wealth_management_portal_portfolio_data_access.config import config


class DataApiConnection:
    """Wrapper to make Data API look like redshift_connector for compatibility."""

    def __init__(self, workgroup: str, database: str, region: str):
        self.client = boto3.client("redshift-data", region_name=region)
        self.workgroup = workgroup
        self.database = database

    def cursor(self):
        return DataApiCursor(self.client, self.workgroup, self.database)

    def commit(self):
        pass  # Data API auto-commits

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class DataApiCursor:
    """Cursor wrapper for Data API."""

    def __init__(self, client, workgroup: str, database: str):
        self.client = client
        self.workgroup = workgroup
        self.database = database
        self.results = []
        self.description = None  # Column metadata
        self._column_names = []

    def execute(self, sql: str, params=None):
        kwargs = dict(WorkgroupName=self.workgroup, Database=self.database, Sql=sql)
        if params:
            kwargs["Parameters"] = [{"name": str(i), "value": str(p)} for i, p in enumerate(params)]
            # Redshift Data API uses :0, :1, ... named placeholders; rewrite %s markers
            for i in range(len(params)):
                sql = sql.replace("%s", f":{i}", 1)
            kwargs["Sql"] = sql

        response = self.client.execute_statement(**kwargs)

        statement_id = response["Id"]

        # Wait for completion
        while True:
            status = self.client.describe_statement(Id=statement_id)
            if status["Status"] in ["FINISHED", "FAILED", "ABORTED"]:
                break
            time.sleep(0.1)

        if status["Status"] == "FINISHED":
            result = self.client.get_statement_result(Id=statement_id)
            self.results = result.get("Records", [])

            # Build column metadata
            if result.get("ColumnMetadata"):
                self._column_names = [col["name"] for col in result["ColumnMetadata"]]
                self.description = [
                    (col["name"], None, None, None, None, None, None) for col in result["ColumnMetadata"]
                ]
        else:
            self.results = []
            self.description = None

    def fetchall(self):
        # Convert Data API format to tuple format (not dict)
        rows = []
        for record in self.results:
            row = []
            for field in record:
                # Data API returns fields as dicts like {'stringValue': 'foo'} or {'isNull': True}
                if not field or field.get("isNull"):
                    row.append(None)
                else:
                    # Get the actual value (remove the type key)
                    value = next((v for k, v in field.items() if k != "isNull"), None)
                    row.append(value)
            rows.append(tuple(row))
        return rows

    def fetchone(self):
        if self.results:
            record = self.results[0]
            row = []
            for field in record:
                if not field or field.get("isNull"):
                    row.append(None)
                else:
                    value = next((v for k, v in field.items() if k != "isNull"), None)
                    row.append(value)
            return tuple(row)
        return None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def data_api_connection_factory(
    workgroup: str | None = None,
    database: str | None = None,
    region: str | None = None,
) -> DataApiConnection:
    """Create a DataApiConnection using config defaults for any unspecified parameters."""
    return DataApiConnection(
        workgroup=workgroup or config.workgroup,
        database=database or config.database,
        region=region or config.region,
    )
