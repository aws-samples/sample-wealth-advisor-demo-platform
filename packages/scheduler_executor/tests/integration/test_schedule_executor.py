"""Integration tests for schedule_executor (real DynamoDB, mocked agent)."""

import io
import json
import os
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import boto3
import pytest

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("SCHEDULES_TABLE_NAME") or not os.environ.get("ROUTING_AGENT_ARN"),
        reason="SCHEDULES_TABLE_NAME and ROUTING_AGENT_ARN env vars required",
    ),
    pytest.mark.integration,
]


@pytest.fixture
def test_schedule():
    """Write a test schedule to real DynamoDB and clean up after."""
    schedule_id = f"integ-test-{uuid.uuid4()}"
    user_id = "integ-test-executor-user"
    ddb = boto3.resource("dynamodb")
    schedules_table = ddb.Table(os.environ["SCHEDULES_TABLE_NAME"])

    item = {
        "PK": f"USER#{user_id}",
        "SK": f"SCHEDULE#{schedule_id}",
        "GSI1PK": f"SCHEDULE#{schedule_id}",
        "GSI1SK": f"USER#{user_id}",
        "schedule_id": schedule_id,
        "user_id": user_id,
        "name": "Integration Test Schedule",
        "task_message": "Run integration test task",
        "email": "test@example.com",
        "delivery_method": "email",
        "enabled": True,
        "last_status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    schedules_table.put_item(Item=item)

    yield schedule_id, user_id

    # Teardown
    schedules_table.delete_item(Key={"PK": f"USER#{user_id}", "SK": f"SCHEDULE#{schedule_id}"})
    results_table = ddb.Table(os.environ["SCHEDULE_RESULTS_TABLE_NAME"])
    from boto3.dynamodb.conditions import Key

    results = results_table.query(KeyConditionExpression=Key("PK").eq(f"SCHEDULE#{schedule_id}"))
    for r in results.get("Items", []):
        results_table.delete_item(Key={"PK": r["PK"], "SK": r["SK"]})


def test_executor_writes_result_and_updates_schedule(test_schedule):
    """Executor reads schedule, calls agent (mocked), writes result, updates schedule."""
    schedule_id, user_id = test_schedule

    body = {"result": {"artifacts": [{"parts": [{"kind": "text", "text": "Integration test result."}]}]}}
    mock_agent = MagicMock()
    mock_agent.invoke_agent_runtime.return_value = {"response": io.BytesIO(json.dumps(body).encode())}

    from wealth_management_portal_scheduler_executor.lambda_functions import schedule_executor

    schedule_executor._dynamodb = None
    schedule_executor._agentcore_client = None

    ctx = MagicMock()
    ctx.function_name = "schedule-executor"

    with patch.object(schedule_executor, "_get_agentcore_client", return_value=mock_agent):
        schedule_executor.lambda_handler({"schedule_id": schedule_id}, ctx)

    ddb = boto3.resource("dynamodb")

    # Verify result record written
    results_table = ddb.Table(os.environ["SCHEDULE_RESULTS_TABLE_NAME"])
    from boto3.dynamodb.conditions import Key

    results = results_table.query(KeyConditionExpression=Key("PK").eq(f"SCHEDULE#{schedule_id}"))
    assert len(results["Items"]) == 1
    assert results["Items"][0]["status"] == "success"

    # Verify schedule updated
    schedules_table = ddb.Table(os.environ["SCHEDULES_TABLE_NAME"])
    item = schedules_table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"SCHEDULE#{schedule_id}"})["Item"]
    assert item["last_status"] == "success"
    assert "last_run_at" in item
