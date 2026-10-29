"""DynamoDB-backed repository for DD sessions, reports, and events."""

from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any

import boto3


def _float_to_decimal(obj: Any) -> Any:
    """Convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_float_to_decimal(i) for i in obj]
    return obj


def _get_table(env_var: str):
    table_name = os.environ.get(env_var)
    if not table_name:
        return None
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(table_name)


def _decimal_to_float(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(i) for i in obj]
    return obj


class DDRepository:
    def __init__(self):
        self._sessions_table = _get_table("DD_SESSIONS_TABLE")
        self._reports_table = _get_table("DD_REPORTS_TABLE")

    @property
    def is_available(self) -> bool:
        return self._sessions_table is not None

    def create_session(self, session_data: dict) -> None:
        if not self._sessions_table:
            return
        item = {
            "session_id": session_data["session_id"],
            "portfolio_id": session_data["portfolio_id"],
            "portfolio_name": session_data["portfolio_name"],
            "manager_name": session_data.get("manager_name", ""),
            "status": session_data["status"],
            "started_at": session_data["started_at"],
            "completed_at": session_data.get("completed_at"),
            "overall_score": session_data.get("overall_score"),
            "recommendation": session_data.get("recommendation"),
            "hitl_required": session_data.get("hitl_required", False),
            "events": [],
            "hitl_flags": [],
        }
        item = {k: v for k, v in item.items() if v is not None}
        self._sessions_table.put_item(Item=_float_to_decimal(item))

    def list_sessions(self) -> list[dict]:
        if not self._sessions_table:
            return []
        projection = (
            "session_id, portfolio_id, portfolio_name, #s,"
            " started_at, completed_at, overall_score, recommendation, hitl_required"
        )
        resp = self._sessions_table.scan(
            ProjectionExpression=projection,
            ExpressionAttributeNames={"#s": "status"},
        )
        items = resp.get("Items", [])
        return [_decimal_to_float(item) for item in items]

    def get_session(self, session_id: str) -> dict | None:
        if not self._sessions_table:
            return None
        resp = self._sessions_table.get_item(Key={"session_id": session_id})
        item = resp.get("Item")
        return _decimal_to_float(item) if item else None

    def update_session(self, session_id: str, updates: dict) -> None:
        if not self._sessions_table:
            return
        expr_parts = []
        expr_values = {}
        expr_names = {}
        for i, (key, value) in enumerate(updates.items()):
            attr_name = f"#attr{i}"
            attr_val = f":val{i}"
            expr_parts.append(f"{attr_name} = {attr_val}")
            expr_names[attr_name] = key
            expr_values[attr_val] = value

        self._sessions_table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET " + ", ".join(expr_parts),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=_float_to_decimal(expr_values),
        )

    def append_event(self, session_id: str, event: dict) -> None:
        if not self._sessions_table:
            return
        self._sessions_table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET #events = list_append(if_not_exists(#events, :empty), :evt)",
            ExpressionAttributeNames={"#events": "events"},
            ExpressionAttributeValues=_float_to_decimal({":evt": [event], ":empty": []}),
        )

    def get_events(self, session_id: str) -> list[dict]:
        session = self.get_session(session_id)
        if not session:
            return []
        return session.get("events", [])

    def save_report(self, session_id: str, report: dict) -> None:
        if not self._reports_table:
            return
        self._reports_table.put_item(
            Item={
                "session_id": session_id,
                "report_json": json.dumps(report, default=str),
            }
        )

    def get_report(self, session_id: str) -> dict | None:
        if not self._reports_table:
            return None
        resp = self._reports_table.get_item(Key={"session_id": session_id})
        item = resp.get("Item")
        if not item:
            return None
        return json.loads(item["report_json"])

    def set_hitl_flags(self, session_id: str, flags: list[dict]) -> None:
        self.update_session(session_id, {"hitl_flags": flags})

    def get_hitl_flags(self, session_id: str) -> list[dict]:
        session = self.get_session(session_id)
        if not session:
            return []
        return session.get("hitl_flags", [])

    def update_hitl_flag(self, session_id: str, flag_id: str, updates: dict) -> None:
        flags = self.get_hitl_flags(session_id)
        for flag in flags:
            if flag.get("flag_id") == flag_id:
                flag.update(updates)
                break
        self.set_hitl_flags(session_id, flags)
