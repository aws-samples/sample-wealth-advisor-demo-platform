import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "SchedulerGateway")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "SchedulerGateway")
os.environ.setdefault("SCHEDULES_TABLE_NAME", "SchedulesTable")
os.environ.setdefault("SCHEDULE_RESULTS_TABLE_NAME", "ScheduleResultsTable")
os.environ.setdefault("EXECUTOR_LAMBDA_ARN", "arn:aws:lambda:us-east-1:123:function:executor")
os.environ.setdefault("EVENTBRIDGE_ROLE_ARN", "arn:aws:iam::123:role/eb-role")

from wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway import lambda_handler  # noqa: E402


def _context(tool_name: str):
    ctx = MagicMock()
    ctx.client_context.custom = {"bedrockAgentCoreToolName": f"gateway___scheduler___{tool_name}"}
    return ctx


def _sample_schedule():
    return {
        "schedule_id": "s1",
        "user_id": "u1",
        "name": "Test",
        "task_message": "do something",
        "cron_expression": "cron(0 16 * * ? *)",
        "timezone": "UTC",
        "email": "test@example.com",
        "delivery_method": "email",
        "enabled": True,
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
        "last_status": "pending",
        "PK": "USER#u1",
        "SK": "SCHEDULE#s1",
        "GSI1PK": "SCHEDULE#s1",
        "GSI1SK": "USER#u1",
    }


@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway.eventbridge")
@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway._repo")
def test_create_schedule_success(mock_repo_fn, mock_eb):
    mock_repo = MagicMock()
    mock_repo_fn.return_value = mock_repo
    mock_eb.create_schedule.return_value = "user-schedule-s1"

    event = {
        "cron_expression": "cron(0 16 * * ? *)",
        "task_message": "do something",
        "name": "Daily Task",
        "user_id": "u1",
        "email": "test@example.com",
    }
    result = lambda_handler(event, _context("create_schedule"))
    assert "schedule_id" in result
    mock_repo.create_schedule.assert_called_once()
    mock_eb.create_schedule.assert_called_once()


@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway.eventbridge")
@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway._repo")
def test_create_schedule_invalid_cron(mock_repo_fn, mock_eb):
    event = {
        "cron_expression": "0 16 * * *",
        "task_message": "do something",
        "name": "Daily Task",
        "user_id": "u1",
        "email": "test@example.com",
    }
    result = lambda_handler(event, _context("create_schedule"))
    assert "error" in result
    mock_repo_fn.assert_not_called()
    mock_eb.create_schedule.assert_not_called()


@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway.eventbridge")
@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway._repo")
def test_create_schedule_eventbridge_failure_rolls_back(mock_repo_fn, mock_eb):
    mock_repo = MagicMock()
    mock_repo_fn.return_value = mock_repo
    mock_eb.create_schedule.side_effect = Exception("EB down")

    event = {
        "cron_expression": "cron(0 16 * * ? *)",
        "task_message": "do something",
        "name": "Daily Task",
        "user_id": "u1",
        "email": "test@example.com",
    }
    result = lambda_handler(event, _context("create_schedule"))
    assert "error" in result
    mock_repo.delete_schedule.assert_called_once()


@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway._repo")
def test_list_schedules(mock_repo_fn):
    mock_repo = MagicMock()
    mock_repo_fn.return_value = mock_repo
    mock_repo.list_schedules_by_user.return_value = [_sample_schedule()]

    result = lambda_handler({"user_id": "u1"}, _context("list_schedules"))
    assert "schedules" in result
    assert len(result["schedules"]) == 1
    mock_repo.list_schedules_by_user.assert_called_once_with("u1")


@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway.eventbridge")
@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway._repo")
def test_delete_schedule(mock_repo_fn, mock_eb):
    mock_repo = MagicMock()
    mock_repo_fn.return_value = mock_repo
    mock_repo.get_schedule_by_id.return_value = _sample_schedule()

    result = lambda_handler({"schedule_id": "s1", "user_id": "u1"}, _context("delete_schedule"))
    assert "message" in result
    mock_repo.delete_schedule.assert_called_once_with("u1", "s1")
    mock_eb.delete_schedule.assert_called_once_with("s1")


@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway._repo")
def test_delete_schedule_not_found(mock_repo_fn):
    mock_repo = MagicMock()
    mock_repo_fn.return_value = mock_repo
    mock_repo.get_schedule_by_id.return_value = None

    result = lambda_handler({"schedule_id": "s1", "user_id": "u1"}, _context("delete_schedule"))
    assert "error" in result


@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway.eventbridge")
@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway._repo")
def test_toggle_schedule(mock_repo_fn, mock_eb):
    mock_repo = MagicMock()
    mock_repo_fn.return_value = mock_repo
    mock_repo.get_schedule_by_id.return_value = _sample_schedule()

    result = lambda_handler({"schedule_id": "s1", "user_id": "u1", "enabled": False}, _context("toggle_schedule"))
    assert "message" in result
    mock_repo.toggle_enabled.assert_called_once_with("u1", "s1", False)
    mock_eb.update_schedule_state.assert_called_once_with("s1", False)


def test_unknown_tool():
    result = lambda_handler({}, _context("nonexistent_tool"))
    assert "error" in result


@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway.eventbridge")
@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway._repo")
def test_delete_schedule_wrong_user(mock_repo_fn, mock_eb):
    mock_repo = MagicMock()
    mock_repo_fn.return_value = mock_repo
    mock_repo.get_schedule_by_id.return_value = _sample_schedule()  # owned by u1

    result = lambda_handler({"schedule_id": "s1", "user_id": "attacker"}, _context("delete_schedule"))
    assert "error" in result
    assert "Not authorized" in result["error"]
    mock_repo.delete_schedule.assert_not_called()
    mock_eb.delete_schedule.assert_not_called()


@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway.eventbridge")
@patch("wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway._repo")
def test_toggle_schedule_wrong_user(mock_repo_fn, mock_eb):
    mock_repo = MagicMock()
    mock_repo_fn.return_value = mock_repo
    mock_repo.get_schedule_by_id.return_value = _sample_schedule()  # owned by u1

    result = lambda_handler({"schedule_id": "s1", "user_id": "attacker", "enabled": False}, _context("toggle_schedule"))
    assert "error" in result
    assert "Not authorized" in result["error"]
    mock_repo.toggle_enabled.assert_not_called()
    mock_eb.update_schedule_state.assert_not_called()
