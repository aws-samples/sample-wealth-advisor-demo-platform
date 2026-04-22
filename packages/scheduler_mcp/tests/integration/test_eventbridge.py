"""Integration tests for EventBridge manager against real EventBridge Scheduler."""

import contextlib
import os

import boto3
import pytest

from wealth_management_portal_scheduler_mcp import eventbridge

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("EXECUTOR_LAMBDA_ARN") or not os.environ.get("EVENTBRIDGE_ROLE_ARN"),
        reason="EXECUTOR_LAMBDA_ARN or EVENTBRIDGE_ROLE_ARN not set",
    ),
    pytest.mark.integration,
]

SCHEDULE_ID = "integration-test-eb-001"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    with contextlib.suppress(Exception):
        eventbridge.delete_schedule(SCHEDULE_ID)


def _describe():
    return boto3.client("scheduler").get_schedule(Name=f"user-schedule-{SCHEDULE_ID}")


def test_create_verify_toggle_delete():
    # create
    name = eventbridge.create_schedule(SCHEDULE_ID, "cron(0 16 * * ? *)")
    assert name == f"user-schedule-{SCHEDULE_ID}"

    # verify exists and enabled
    desc = _describe()
    assert desc["State"] == "ENABLED"
    assert desc["ScheduleExpression"] == "cron(0 16 * * ? *)"

    # toggle disabled
    eventbridge.update_schedule_state(SCHEDULE_ID, False)
    desc = _describe()
    assert desc["State"] == "DISABLED"

    # toggle enabled
    eventbridge.update_schedule_state(SCHEDULE_ID, True)
    desc = _describe()
    assert desc["State"] == "ENABLED"

    # delete and verify gone
    eventbridge.delete_schedule(SCHEDULE_ID)
    client = boto3.client("scheduler")
    with pytest.raises(client.exceptions.ResourceNotFoundException):
        client.get_schedule(Name=f"user-schedule-{SCHEDULE_ID}")
