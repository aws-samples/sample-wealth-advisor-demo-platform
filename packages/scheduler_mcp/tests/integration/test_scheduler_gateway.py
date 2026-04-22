"""Integration tests for the scheduler_gateway Lambda handler (real DynamoDB + EventBridge)."""

import contextlib
import os
from unittest.mock import MagicMock

import boto3
import pytest

from wealth_management_portal_scheduler_mcp import eventbridge
from wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway import lambda_handler
from wealth_management_portal_scheduler_mcp.repository import Repository

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("SCHEDULES_TABLE_NAME")
        or not os.environ.get("EXECUTOR_LAMBDA_ARN")
        or not os.environ.get("EVENTBRIDGE_ROLE_ARN"),
        reason="Required env vars not set",
    ),
    pytest.mark.integration,
]

USER_ID = "integration-test-gw-user"


def _context(tool_name: str):
    ctx = MagicMock()
    ctx.client_context.custom = {"bedrockAgentCoreToolName": f"gateway___scheduler___{tool_name}"}
    return ctx


@pytest.fixture
def created_schedule_id():
    """Create a schedule via handler and yield its ID; clean up after test."""
    result = lambda_handler(
        {
            "cron_expression": "cron(0 16 * * ? *)",
            "task_message": "integration test task",
            "name": "Integration Test",
            "user_id": USER_ID,
            "email": "test@example.com",
        },
        _context("create_schedule"),
    )
    assert "schedule_id" in result, f"create_schedule failed: {result}"
    schedule_id = result["schedule_id"]

    yield schedule_id

    # teardown: delete from DynamoDB + EventBridge (best-effort)
    repo = Repository()
    repo.delete_schedule(USER_ID, schedule_id)
    with contextlib.suppress(Exception):
        eventbridge.delete_schedule(schedule_id)


def test_create_schedule_persists_to_dynamodb_and_eventbridge(created_schedule_id):
    schedule_id = created_schedule_id

    # DynamoDB record exists
    repo = Repository()
    item = repo.get_schedule_by_id(schedule_id)
    assert item is not None
    assert item["user_id"] == USER_ID
    assert item["enabled"] is True

    # EventBridge schedule exists
    desc = boto3.client("scheduler").get_schedule(Name=f"user-schedule-{schedule_id}")
    assert desc["State"] == "ENABLED"


def test_list_schedules_returns_created(created_schedule_id):
    schedule_id = created_schedule_id
    result = lambda_handler({"user_id": USER_ID}, _context("list_schedules"))
    assert "schedules" in result
    ids = [s["schedule_id"] for s in result["schedules"]]
    assert schedule_id in ids


def test_toggle_schedule_updates_eventbridge(created_schedule_id):
    schedule_id = created_schedule_id

    result = lambda_handler(
        {"schedule_id": schedule_id, "user_id": USER_ID, "enabled": False},
        _context("toggle_schedule"),
    )
    assert "message" in result

    desc = boto3.client("scheduler").get_schedule(Name=f"user-schedule-{schedule_id}")
    assert desc["State"] == "DISABLED"

    repo = Repository()
    item = repo.get_schedule_by_id(schedule_id)
    assert item["enabled"] is False


def test_delete_schedule_removes_dynamodb_and_eventbridge(created_schedule_id):
    schedule_id = created_schedule_id

    result = lambda_handler(
        {"schedule_id": schedule_id, "user_id": USER_ID},
        _context("delete_schedule"),
    )
    assert "message" in result

    # DynamoDB gone
    repo = Repository()
    assert repo.get_schedule_by_id(schedule_id) is None

    # EventBridge gone
    client = boto3.client("scheduler")
    with pytest.raises(client.exceptions.ResourceNotFoundException):
        client.get_schedule(Name=f"user-schedule-{schedule_id}")
