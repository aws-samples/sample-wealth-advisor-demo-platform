"""DynamoDB repository for Schedules and Schedule Results tables."""

import os
from datetime import UTC, datetime

import boto3
from boto3.dynamodb.conditions import Key


class Repository:
    def __init__(self):
        dynamodb = boto3.resource("dynamodb")
        self._schedules = dynamodb.Table(os.environ["SCHEDULES_TABLE_NAME"])
        self._results = dynamodb.Table(os.environ["SCHEDULE_RESULTS_TABLE_NAME"])

    # ------------------------------------------------------------------
    # Schedules table
    # ------------------------------------------------------------------

    def create_schedule(self, item: dict) -> dict:
        """Write a schedule item. item must include all required fields."""
        self._schedules.put_item(Item=item)
        return item

    def get_schedule_by_id(self, schedule_id: str) -> dict | None:
        """Lookup schedule via GSI1 (GSI1PK = SCHEDULE#{schedule_id})."""
        resp = self._schedules.query(
            IndexName="GSI1",
            KeyConditionExpression=Key("GSI1PK").eq(f"SCHEDULE#{schedule_id}"),
        )
        items = resp.get("Items", [])
        if not items:
            return None
        # GSI is eventually consistent; re-fetch via primary key for strong consistency
        key = {"PK": items[0]["PK"], "SK": items[0]["SK"]}
        result = self._schedules.get_item(Key=key, ConsistentRead=True)
        return result.get("Item")

    def list_schedules_by_user(self, user_id: str) -> list[dict]:
        """Return all schedules for a user (PK = USER#{user_id})."""
        # TODO: handle pagination for large result sets (>1MB)
        resp = self._schedules.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}"),
        )
        return resp.get("Items", [])

    def delete_schedule(self, user_id: str, schedule_id: str) -> None:
        self._schedules.delete_item(Key={"PK": f"USER#{user_id}", "SK": f"SCHEDULE#{schedule_id}"})

    def update_last_run(self, user_id: str, schedule_id: str, status: str, error: str | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        expr = "SET last_run_at = :ts, last_status = :s, updated_at = :ts2"
        values: dict = {":ts": now, ":ts2": now, ":s": status}
        if error is not None:
            expr += ", last_error = :e"
            values[":e"] = error
        self._schedules.update_item(
            Key={"PK": f"USER#{user_id}", "SK": f"SCHEDULE#{schedule_id}"},
            UpdateExpression=expr,
            ExpressionAttributeValues=values,
        )

    def toggle_enabled(self, user_id: str, schedule_id: str, enabled: bool) -> None:
        now = datetime.now(UTC).isoformat()
        self._schedules.update_item(
            Key={"PK": f"USER#{user_id}", "SK": f"SCHEDULE#{schedule_id}"},
            UpdateExpression="SET enabled = :e, updated_at = :ts",
            ExpressionAttributeValues={":e": enabled, ":ts": now},
        )

    # ------------------------------------------------------------------
    # Schedule Results table
    # ------------------------------------------------------------------

    def create_result(self, item: dict) -> dict:
        """Write a result item. item must include PK, SK, and ttl."""
        self._results.put_item(Item=item)
        return item

    def get_results(self, schedule_id: str, limit: int = 20) -> list[dict]:
        """Return results for a schedule ordered by SK (timestamp) descending."""
        resp = self._results.query(
            KeyConditionExpression=Key("PK").eq(f"SCHEDULE#{schedule_id}"),
            ScanIndexForward=False,
            Limit=limit,
        )
        return resp.get("Items", [])
