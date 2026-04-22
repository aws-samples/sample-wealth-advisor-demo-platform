"""Unit tests for schedule_executor Lambda handler."""

import os
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

# Set required env vars before importing handler
os.environ.setdefault("SCHEDULES_TABLE_NAME", "test-schedules")
os.environ.setdefault("SCHEDULE_RESULTS_TABLE_NAME", "test-results")
os.environ.setdefault("ROUTING_AGENT_ARN", "arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/test-agent")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from wealth_management_portal_scheduler_executor.lambda_functions import schedule_executor  # noqa: E402

SCHEDULE_ID = "sched-001"
USER_ID = "user-001"
SCHEDULE_ITEM = {
    "PK": f"USER#{USER_ID}",
    "SK": f"SCHEDULE#{SCHEDULE_ID}",
    "GSI1PK": f"SCHEDULE#{SCHEDULE_ID}",
    "GSI1SK": f"USER#{USER_ID}",
    "schedule_id": SCHEDULE_ID,
    "user_id": USER_ID,
    "name": "Daily Market Analysis",
    "task_message": "Give me the latest market themes",
    "email": "advisor@example.com",
    "delivery_method": "email",
    "enabled": True,
    "last_status": "pending",
}


@pytest.fixture(autouse=True)
def reset_clients():
    """Reset cached module-level clients between tests."""
    schedule_executor._dynamodb = None
    schedule_executor._http = None
    schedule_executor._secrets_client = None
    schedule_executor._token_cache["token"] = None
    schedule_executor._token_cache["expires_at"] = 0
    yield
    schedule_executor._dynamodb = None
    schedule_executor._http = None
    schedule_executor._secrets_client = None
    schedule_executor._token_cache["token"] = None
    schedule_executor._token_cache["expires_at"] = 0


@pytest.fixture
def dynamodb_tables():
    with mock_aws():
        ddb = boto3.resource("dynamodb")

        schedules_table = ddb.create_table(
            TableName="test-schedules",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [{"AttributeName": "GSI1PK", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        results_table = ddb.create_table(
            TableName="test-results",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        schedules_table.put_item(Item=SCHEDULE_ITEM)
        yield schedules_table, results_table


def _make_context():
    ctx = MagicMock()
    ctx.function_name = "schedule-executor"
    return ctx


def _mock_agent_success(monkeypatch):
    """Patch _invoke_agent to return a canned response."""
    mock_invoke = MagicMock(return_value="Market analysis complete.")
    monkeypatch.setattr(schedule_executor, "_invoke_agent", mock_invoke)
    return mock_invoke


def test_success_flow(dynamodb_tables, monkeypatch):
    """EventBridge event → reads schedule → calls agent → records success."""
    schedules_table, results_table = dynamodb_tables
    mock_invoke = _mock_agent_success(monkeypatch)

    schedule_executor.lambda_handler({"schedule_id": SCHEDULE_ID}, _make_context())

    mock_invoke.assert_called_once()
    call_args = mock_invoke.call_args
    # _invoke_agent(message, user_id)
    assert call_args[0][1] == USER_ID

    # Result written
    from boto3.dynamodb.conditions import Key

    results = results_table.query(KeyConditionExpression=Key("PK").eq(f"SCHEDULE#{SCHEDULE_ID}"))
    assert len(results["Items"]) == 1
    assert results["Items"][0]["status"] == "success"

    # Schedule updated
    item = schedules_table.get_item(Key={"PK": f"USER#{USER_ID}", "SK": f"SCHEDULE#{SCHEDULE_ID}"})["Item"]
    assert item["last_status"] == "success"
    assert "last_run_at" in item


def test_augmented_message_format(dynamodb_tables, monkeypatch):
    """Augmented message includes [Scheduled Task:] prefix and delivery instructions."""
    mock_invoke = _mock_agent_success(monkeypatch)

    schedule_executor.lambda_handler({"schedule_id": SCHEDULE_ID}, _make_context())

    message = mock_invoke.call_args[0][0]
    assert "[Scheduled Task: Daily Market Analysis]" in message
    assert "Task: Give me the latest market themes" in message
    assert "Deliver results via email to: advisor@example.com" in message


def test_schedule_not_found(dynamodb_tables, monkeypatch):
    """Missing schedule → logs error, no agent call, no result."""
    mock_invoke = MagicMock()
    monkeypatch.setattr(schedule_executor, "_invoke_agent", mock_invoke)

    schedule_executor.lambda_handler({"schedule_id": "nonexistent"}, _make_context())

    mock_invoke.assert_not_called()
    _, results_table = dynamodb_tables
    from boto3.dynamodb.conditions import Key

    results = results_table.query(KeyConditionExpression=Key("PK").eq("SCHEDULE#nonexistent"))
    assert len(results["Items"]) == 0


def test_disabled_schedule(dynamodb_tables, monkeypatch):
    """Disabled schedule → skips execution, no agent call."""
    schedules_table, _ = dynamodb_tables
    schedules_table.update_item(
        Key={"PK": f"USER#{USER_ID}", "SK": f"SCHEDULE#{SCHEDULE_ID}"},
        UpdateExpression="SET enabled = :e",
        ExpressionAttributeValues={":e": False},
    )

    mock_invoke = MagicMock()
    monkeypatch.setattr(schedule_executor, "_invoke_agent", mock_invoke)

    schedule_executor.lambda_handler({"schedule_id": SCHEDULE_ID}, _make_context())

    mock_invoke.assert_not_called()


def test_agent_failure_records_failed_result(dynamodb_tables, monkeypatch):
    """Agent failure → records failed status + error in results table."""
    mock_invoke = MagicMock(side_effect=Exception("Agent unavailable"))
    monkeypatch.setattr(schedule_executor, "_invoke_agent", mock_invoke)

    schedule_executor.lambda_handler({"schedule_id": SCHEDULE_ID}, _make_context())

    from boto3.dynamodb.conditions import Key

    _, results_table = dynamodb_tables
    results = results_table.query(KeyConditionExpression=Key("PK").eq(f"SCHEDULE#{SCHEDULE_ID}"))
    assert len(results["Items"]) == 1
    assert results["Items"][0]["status"] == "failed"
    assert "Agent unavailable" in results["Items"][0]["error"]

    schedules_table, _ = dynamodb_tables
    item = schedules_table.get_item(Key={"PK": f"USER#{USER_ID}", "SK": f"SCHEDULE#{SCHEDULE_ID}"})["Item"]
    assert item["last_status"] == "failed"
    assert "Agent unavailable" in item["last_error"]
