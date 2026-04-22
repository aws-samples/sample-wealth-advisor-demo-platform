"""EventBridge Scheduler manager."""

import json
import os

import boto3

_scheduler_client = None


def _client():
    global _scheduler_client
    if _scheduler_client is None:
        _scheduler_client = boto3.client("scheduler")
    return _scheduler_client


def _schedule_name(schedule_id: str) -> str:
    return f"user-schedule-{schedule_id}"


def create_schedule(schedule_id: str, cron_expression: str, timezone: str = "UTC") -> str:
    """Create an EventBridge schedule. Returns the schedule name."""
    name = _schedule_name(schedule_id)
    _client().create_schedule(
        Name=name,
        ScheduleExpression=cron_expression,
        ScheduleExpressionTimezone=timezone,
        FlexibleTimeWindow={"Mode": "OFF"},
        Target={
            "Arn": os.environ["EXECUTOR_LAMBDA_ARN"],
            "RoleArn": os.environ["EVENTBRIDGE_ROLE_ARN"],
            "Input": json.dumps({"schedule_id": schedule_id}),
        },
        State="ENABLED",
    )
    return name


def delete_schedule(schedule_id: str) -> None:
    _client().delete_schedule(Name=_schedule_name(schedule_id))


def update_schedule_state(schedule_id: str, enabled: bool) -> None:
    """Enable or disable an existing EventBridge schedule."""
    name = _schedule_name(schedule_id)
    client = _client()
    existing = client.get_schedule(Name=name)
    # Extract only required fields to avoid passing read-only metadata
    target = existing["Target"]
    update_kwargs = {
        "Name": name,
        "ScheduleExpression": existing["ScheduleExpression"],
        "FlexibleTimeWindow": {"Mode": existing["FlexibleTimeWindow"]["Mode"]},
        "Target": {"Arn": target["Arn"], "RoleArn": target["RoleArn"], "Input": target.get("Input", "")},
        "State": "ENABLED" if enabled else "DISABLED",
    }
    if existing.get("ScheduleExpressionTimezone"):
        update_kwargs["ScheduleExpressionTimezone"] = existing["ScheduleExpressionTimezone"]
    client.update_schedule(**update_kwargs)
