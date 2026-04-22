import json
from unittest.mock import MagicMock, patch

import pytest

from wealth_management_portal_scheduler_mcp import eventbridge


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("EXECUTOR_LAMBDA_ARN", "arn:aws:lambda:us-east-1:123:function:executor")
    monkeypatch.setenv("EVENTBRIDGE_ROLE_ARN", "arn:aws:iam::123:role/eb-role")


@pytest.fixture
def mock_client():
    with patch("wealth_management_portal_scheduler_mcp.eventbridge._client") as m:
        client = MagicMock()
        m.return_value = client
        yield client


def test_create_schedule(mock_client):
    name = eventbridge.create_schedule("abc-123", "cron(0 16 * * ? *)")
    assert name == "user-schedule-abc-123"
    mock_client.create_schedule.assert_called_once_with(
        Name="user-schedule-abc-123",
        ScheduleExpression="cron(0 16 * * ? *)",
        ScheduleExpressionTimezone="UTC",
        FlexibleTimeWindow={"Mode": "OFF"},
        Target={
            "Arn": "arn:aws:lambda:us-east-1:123:function:executor",
            "RoleArn": "arn:aws:iam::123:role/eb-role",
            "Input": json.dumps({"schedule_id": "abc-123"}),
        },
        State="ENABLED",
    )


def test_delete_schedule(mock_client):
    eventbridge.delete_schedule("abc-123")
    mock_client.delete_schedule.assert_called_once_with(Name="user-schedule-abc-123")


def test_update_schedule_state_enabled(mock_client):
    mock_client.get_schedule.return_value = {
        "ScheduleExpression": "cron(0 16 * * ? *)",
        "FlexibleTimeWindow": {"Mode": "OFF"},
        "Target": {
            "Arn": "arn:aws:lambda:us-east-1:123:function:executor",
            "RoleArn": "arn:aws:iam::123:role/eb-role",
            "Input": '{"schedule_id": "abc-123"}',
        },
    }
    eventbridge.update_schedule_state("abc-123", True)
    mock_client.update_schedule.assert_called_once()
    _, kwargs = mock_client.update_schedule.call_args
    assert kwargs["State"] == "ENABLED"


def test_update_schedule_state_disabled(mock_client):
    mock_client.get_schedule.return_value = {
        "ScheduleExpression": "cron(0 16 * * ? *)",
        "FlexibleTimeWindow": {"Mode": "OFF"},
        "Target": {
            "Arn": "arn:aws:lambda:us-east-1:123:function:executor",
            "RoleArn": "arn:aws:iam::123:role/eb-role",
            "Input": '{"schedule_id": "abc-123"}',
        },
    }
    eventbridge.update_schedule_state("abc-123", False)
    _, kwargs = mock_client.update_schedule.call_args
    assert kwargs["State"] == "DISABLED"


def test_schedule_name_format():
    assert eventbridge._schedule_name("my-id") == "user-schedule-my-id"
