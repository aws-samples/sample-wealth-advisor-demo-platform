import os
import uuid
from datetime import UTC, datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

from wealth_management_portal_scheduler_mcp import eventbridge, repository
from wealth_management_portal_scheduler_mcp.validator import ValidationError, validate_expression

os.environ["POWERTOOLS_METRICS_NAMESPACE"] = "SchedulerGateway"
os.environ["POWERTOOLS_SERVICE_NAME"] = "SchedulerGateway"

logger: Logger = Logger()
metrics: Metrics = Metrics()
tracer: Tracer = Tracer()


_cached_repo = None


def _repo() -> repository.Repository:
    global _cached_repo
    if _cached_repo is None:
        _cached_repo = repository.Repository()
    return _cached_repo


def _create_schedule(event: dict) -> dict:
    # Validate and normalize the cron/rate expression (fixes LLM formatting issues)
    cron_expression = validate_expression(event["cron_expression"])

    schedule_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    # eventbridge_schedule_name is deterministic — include upfront
    eb_name = f"user-schedule-{schedule_id}"
    item = {
        "PK": f"USER#{event['user_id']}",
        "SK": f"SCHEDULE#{schedule_id}",
        "GSI1PK": f"SCHEDULE#{schedule_id}",
        "GSI1SK": f"USER#{event['user_id']}",
        "schedule_id": schedule_id,
        "user_id": event["user_id"],
        "name": event["name"],
        "task_message": event["task_message"],
        "cron_expression": cron_expression,
        "timezone": event.get("timezone", "UTC"),
        "email": event["email"],
        "delivery_method": "email",
        "enabled": True,
        "eventbridge_schedule_name": eb_name,
        "created_at": now,
        "updated_at": now,
        "last_status": "pending",
    }

    repo = _repo()
    repo.create_schedule(item)

    try:
        eventbridge.create_schedule(schedule_id, cron_expression, item["timezone"])
    except Exception as exc:
        try:
            repo.delete_schedule(event["user_id"], schedule_id)
        except Exception:
            logger.error("Rollback failed — dangling schedule in DynamoDB", extra={"schedule_id": schedule_id})
        raise exc

    return {"schedule_id": schedule_id, "message": f"✓ Scheduled: {event['name']}"}


def _list_schedules(event: dict) -> dict:
    schedules = _repo().list_schedules_by_user(event["user_id"])
    return {
        "schedules": [
            {
                "schedule_id": s["schedule_id"],
                "name": s["name"],
                "cron_expression": s["cron_expression"],
                "enabled": s["enabled"],
                "last_status": s.get("last_status"),
                "last_run_at": s.get("last_run_at"),
            }
            for s in schedules
        ]
    }


def _delete_schedule(event: dict) -> dict:
    repo = _repo()
    schedule = repo.get_schedule_by_id(event["schedule_id"])
    if not schedule:
        return {"error": f"Schedule {event['schedule_id']} not found."}
    # Verify the caller owns this schedule
    if schedule["user_id"] != event["user_id"]:
        return {"error": "Not authorized to delete this schedule."}

    repo.delete_schedule(event["user_id"], event["schedule_id"])
    try:
        eventbridge.delete_schedule(event["schedule_id"])
    except Exception as e:
        logger.warning("EventBridge delete failed", extra={"error": str(e)})

    return {"message": f"Deleted schedule {event['schedule_id']}."}


def _toggle_schedule(event: dict) -> dict:
    repo = _repo()
    schedule = repo.get_schedule_by_id(event["schedule_id"])
    if not schedule:
        return {"error": f"Schedule {event['schedule_id']} not found."}
    # Verify the caller owns this schedule
    if schedule["user_id"] != event["user_id"]:
        return {"error": "Not authorized to modify this schedule."}

    enabled = bool(event["enabled"])
    eventbridge.update_schedule_state(event["schedule_id"], enabled)
    repo.toggle_enabled(event["user_id"], event["schedule_id"], enabled)

    state = "enabled" if enabled else "disabled"
    return {"message": f"Schedule {event['schedule_id']} {state}."}


_DISPATCH = {
    "create_schedule": _create_schedule,
    "list_schedules": _list_schedules,
    "delete_schedule": _delete_schedule,
    "toggle_schedule": _toggle_schedule,
}


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext):
    logger.info("Received event", extra={"event": event})
    metrics.add_metric(name="InvocationCount", unit=MetricUnit.Count, value=1)

    try:
        tool_full_name = context.client_context.custom["bedrockAgentCoreToolName"]
        tool_name = tool_full_name.split("___")[-1]
        logger.info("Dispatching tool", extra={"tool_name": tool_name})

        handler_fn = _DISPATCH.get(tool_name)
        if not handler_fn:
            raise ValueError(f"Unknown tool: {tool_name}")

        result = handler_fn(event)
        metrics.add_metric(name="SuccessCount", unit=MetricUnit.Count, value=1)
        return result

    except ValidationError as e:
        logger.warning("Validation error", extra={"error": str(e)})
        metrics.add_metric(name="ErrorCount", unit=MetricUnit.Count, value=1)
        return {"error": str(e)}
    except Exception as e:
        logger.exception("Tool invocation failed")
        metrics.add_metric(name="ErrorCount", unit=MetricUnit.Count, value=1)
        return {"error": str(e)}
