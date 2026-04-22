"""Integration tests for Repository against real DynamoDB."""

import os
import time
from datetime import UTC, datetime

import pytest

from wealth_management_portal_scheduler_mcp.repository import Repository

pytestmark = [
    pytest.mark.skipif(not os.environ.get("SCHEDULES_TABLE_NAME"), reason="SCHEDULES_TABLE_NAME not set"),
    pytest.mark.integration,
]

USER_ID = "integration-test-user"
SCHEDULE_ID = "integration-test-schedule-001"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    repo = Repository()
    repo.delete_schedule(USER_ID, SCHEDULE_ID)
    # Clean up any results
    results = repo.get_results(SCHEDULE_ID)
    for r in results:
        repo._results.delete_item(Key={"PK": r["PK"], "SK": r["SK"]})


def _sample_item():
    now = datetime.now(UTC).isoformat()
    return {
        "PK": f"USER#{USER_ID}",
        "SK": f"SCHEDULE#{SCHEDULE_ID}",
        "GSI1PK": f"SCHEDULE#{SCHEDULE_ID}",
        "GSI1SK": f"USER#{USER_ID}",
        "schedule_id": SCHEDULE_ID,
        "user_id": USER_ID,
        "name": "Integration Test Schedule",
        "task_message": "run integration test",
        "cron_expression": "cron(0 16 * * ? *)",
        "timezone": "UTC",
        "email": "test@example.com",
        "delivery_method": "email",
        "enabled": True,
        "created_at": now,
        "updated_at": now,
        "last_status": "pending",
    }


def test_full_crud_cycle():
    repo = Repository()

    # create
    repo.create_schedule(_sample_item())

    # read by id via GSI1
    item = repo.get_schedule_by_id(SCHEDULE_ID)
    assert item is not None
    assert item["schedule_id"] == SCHEDULE_ID
    assert item["user_id"] == USER_ID

    # list by user
    schedules = repo.list_schedules_by_user(USER_ID)
    ids = [s["schedule_id"] for s in schedules]
    assert SCHEDULE_ID in ids

    # update_last_run
    repo.update_last_run(USER_ID, SCHEDULE_ID, "success")
    item = repo.get_schedule_by_id(SCHEDULE_ID)
    assert item["last_status"] == "success"
    assert "last_run_at" in item

    # toggle_enabled
    repo.toggle_enabled(USER_ID, SCHEDULE_ID, False)
    item = repo.get_schedule_by_id(SCHEDULE_ID)
    assert item["enabled"] is False

    # delete
    repo.delete_schedule(USER_ID, SCHEDULE_ID)
    assert repo.get_schedule_by_id(SCHEDULE_ID) is None


def test_create_result_and_get_results_with_ttl():
    repo = Repository()
    repo.create_schedule(_sample_item())

    ttl_value = int(time.time()) + 30 * 24 * 3600
    run_ts = datetime.now(UTC).isoformat()
    result_item = {
        "PK": f"SCHEDULE#{SCHEDULE_ID}",
        "SK": f"RUN#{run_ts}",
        "user_id": USER_ID,
        "status": "success",
        "result_summary": "integration test result",
        "ttl": ttl_value,
    }
    repo.create_result(result_item)

    results = repo.get_results(SCHEDULE_ID)
    assert len(results) >= 1
    assert results[0]["status"] == "success"
    assert "ttl" in results[0]
    assert results[0]["ttl"] == ttl_value
