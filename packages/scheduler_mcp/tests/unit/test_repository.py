from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws

from wealth_management_portal_scheduler_mcp.repository import Repository

SCHEDULES_TABLE = "SchedulesTable"
RESULTS_TABLE = "ScheduleResultsTable"


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("SCHEDULES_TABLE_NAME", SCHEDULES_TABLE)
    monkeypatch.setenv("SCHEDULE_RESULTS_TABLE_NAME", RESULTS_TABLE)


@pytest.fixture
def tables():
    with mock_aws():
        ddb = boto3.resource("dynamodb")
        ddb.create_table(
            TableName=SCHEDULES_TABLE,
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
        ddb.create_table(
            TableName=RESULTS_TABLE,
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


def _sample_item(user_id="u1", schedule_id="s1"):
    now = datetime.now(UTC).isoformat()
    return {
        "PK": f"USER#{user_id}",
        "SK": f"SCHEDULE#{schedule_id}",
        "GSI1PK": f"SCHEDULE#{schedule_id}",
        "GSI1SK": f"USER#{user_id}",
        "schedule_id": schedule_id,
        "user_id": user_id,
        "name": "Test",
        "task_message": "do something",
        "cron_expression": "cron(0 16 * * ? *)",
        "timezone": "UTC",
        "email": "test@example.com",
        "delivery_method": "email",
        "enabled": True,
        "created_at": now,
        "updated_at": now,
        "last_status": "pending",
    }


def test_create_and_get_by_id(tables):
    repo = Repository()
    item = _sample_item()
    repo.create_schedule(item)
    result = repo.get_schedule_by_id("s1")
    assert result is not None
    assert result["schedule_id"] == "s1"


def test_get_schedule_by_id_not_found(tables):
    repo = Repository()
    assert repo.get_schedule_by_id("nonexistent") is None


def test_list_schedules_by_user(tables):
    repo = Repository()
    repo.create_schedule(_sample_item("u1", "s1"))
    repo.create_schedule(_sample_item("u1", "s2"))
    repo.create_schedule(_sample_item("u2", "s3"))
    results = repo.list_schedules_by_user("u1")
    assert len(results) == 2


def test_delete_schedule(tables):
    repo = Repository()
    repo.create_schedule(_sample_item())
    repo.delete_schedule("u1", "s1")
    assert repo.get_schedule_by_id("s1") is None


def test_update_last_run(tables):
    repo = Repository()
    repo.create_schedule(_sample_item())
    repo.update_last_run("u1", "s1", "success")
    item = repo.get_schedule_by_id("s1")
    assert item["last_status"] == "success"
    assert "last_run_at" in item


def test_update_last_run_with_error(tables):
    repo = Repository()
    repo.create_schedule(_sample_item())
    repo.update_last_run("u1", "s1", "failed", error="boom")
    item = repo.get_schedule_by_id("s1")
    assert item["last_error"] == "boom"


def test_toggle_enabled(tables):
    repo = Repository()
    repo.create_schedule(_sample_item())
    repo.toggle_enabled("u1", "s1", False)
    item = repo.get_schedule_by_id("s1")
    assert item["enabled"] is False


def test_create_result_and_get_results(tables):
    repo = Repository()
    result_item = {
        "PK": "SCHEDULE#s1",
        "SK": "RUN#2024-01-01T00:00:00",
        "user_id": "u1",
        "status": "success",
        "result_summary": "done",
        "ttl": 9999999999,
    }
    repo.create_result(result_item)
    results = repo.get_results("s1")
    assert len(results) == 1
    assert results[0]["status"] == "success"
