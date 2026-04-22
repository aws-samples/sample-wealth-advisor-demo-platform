"""Executor Lambda — thin orchestrator triggered by EventBridge."""

import json
import os
import uuid
from datetime import UTC, datetime

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Key

os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "ScheduleExecutor")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "ScheduleExecutor")

logger: Logger = Logger()
metrics: Metrics = Metrics()
tracer: Tracer = Tracer()

_dynamodb = None
_http = None
_secrets_client = None
_executor_secret: tuple[str, str] | None = None
_token_cache = {"token": None, "expires_at": 0}


def _get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


def _get_http():
    """Module-level urllib3 pool for connection reuse across invocations."""
    global _http
    if _http is None:
        import urllib3

        _http = urllib3.PoolManager()
    return _http


def _get_executor_secret() -> tuple[str, str]:
    """Read executor client ID and secret from Secrets Manager (cached per cold start)."""
    global _secrets_client, _executor_secret
    if _executor_secret is not None:
        return _executor_secret
    if _secrets_client is None:
        _secrets_client = boto3.client("secretsmanager")
    resp = _secrets_client.get_secret_value(SecretId=os.environ["EXECUTOR_CLIENT_SECRET_ARN"])
    # Secret contains just the client secret string
    client_id = os.environ["EXECUTOR_CLIENT_ID"]
    client_secret = resp["SecretString"]
    _executor_secret = (client_id, client_secret)
    return _executor_secret


def _get_service_token() -> str:
    """Get a cached Cognito service token via client_credentials grant.

    Caches the token with a 60-second pre-expiry buffer to avoid
    using tokens that are about to expire mid-request.
    """
    import time

    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    client_id, client_secret = _get_executor_secret()
    token_endpoint = os.environ["COGNITO_TOKEN_ENDPOINT"]

    import base64

    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    http = _get_http()
    resp = http.request(
        "POST",
        token_endpoint,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth_header}",
        },
        body=b"grant_type=client_credentials&scope=scheduler/execute",
    )
    if resp.status != 200:
        raise RuntimeError(f"Token fetch failed ({resp.status}): {resp.data.decode()}")

    data = json.loads(resp.data)
    _token_cache["token"] = data["access_token"]
    # Cache with 60s pre-expiry buffer
    _token_cache["expires_at"] = now + data.get("expires_in", 3600) - 60
    return _token_cache["token"]


def _get_schedule(schedule_id: str) -> dict | None:
    table = _get_dynamodb().Table(os.environ["SCHEDULES_TABLE_NAME"])
    resp = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"SCHEDULE#{schedule_id}"),
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def _update_last_run(user_id: str, schedule_id: str, status: str, error: str | None = None) -> None:
    table = _get_dynamodb().Table(os.environ["SCHEDULES_TABLE_NAME"])
    now = datetime.now(UTC).isoformat()
    expr = "SET last_run_at = :ts, last_status = :s, updated_at = :ts"
    values: dict = {":ts": now, ":s": status}
    if error is not None:
        expr += ", last_error = :e"
        values[":e"] = error
    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": f"SCHEDULE#{schedule_id}"},
        UpdateExpression=expr,
        ExpressionAttributeValues=values,
    )


def _write_result(schedule_id: str, user_id: str, status: str, result_summary: str = "", error: str = "") -> None:
    table = _get_dynamodb().Table(os.environ["SCHEDULE_RESULTS_TABLE_NAME"])
    now = datetime.now(UTC).isoformat()
    ttl = int(datetime.now(UTC).timestamp()) + 30 * 24 * 3600
    item: dict = {
        "PK": f"SCHEDULE#{schedule_id}",
        "SK": f"RUN#{now}",
        "user_id": user_id,
        "status": status,
        "result_summary": result_summary,
        "ttl": ttl,
    }
    if error:
        item["error"] = error
    table.put_item(Item=item)


def _invoke_agent(message: str, user_id: str) -> str:
    """Invoke routing agent via raw HTTPS with Cognito service token."""
    token = _get_service_token()
    region = os.environ["AWS_REGION_NAME"]
    arn_encoded = __import__("urllib.parse", fromlist=["quote"]).quote(os.environ["ROUTING_AGENT_ARN"], safe="")
    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{arn_encoded}/invocations"

    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {
                "message": {
                    "kind": "message",
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "parts": [{"kind": "text", "text": message}],
                }
            },
        }
    )

    http = _get_http()
    resp = http.request(
        "POST",
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId": user_id,
            "x-amz-bedrock-agentcore-runtime-session-id": f"executor-{uuid.uuid4().hex}",
        },
        body=payload.encode(),
    )

    if resp.status == 401:
        # Token expired mid-flight — clear cache and retry once
        _token_cache["token"] = None
        _token_cache["expires_at"] = 0
        token = _get_service_token()
        resp = http.request(
            "POST",
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId": user_id,
                "x-amz-bedrock-agentcore-runtime-session-id": f"executor-{uuid.uuid4().hex}",
            },
            body=payload.encode(),
        )

    if resp.status != 200:
        raise RuntimeError(f"AgentCore invocation failed ({resp.status}): {resp.data.decode()[:500]}")

    body = json.loads(resp.data)
    result = body.get("result", {})
    for artifact in result.get("artifacts", []):
        for part in artifact.get("parts", []):
            if part.get("kind") == "text" and part.get("text"):
                return part["text"]
    return str(body)


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext):
    logger.info("Received event", extra={"event": event})
    metrics.add_metric(name="InvocationCount", unit=MetricUnit.Count, value=1)

    schedule_id = event.get("schedule_id")
    if not schedule_id:
        logger.error("Missing schedule_id in event", extra={"event": event})
        return

    schedule = _get_schedule(schedule_id)
    if not schedule:
        logger.error("Schedule not found", extra={"schedule_id": schedule_id})
        metrics.add_metric(name="ErrorCount", unit=MetricUnit.Count, value=1)
        return

    if not schedule.get("enabled", True):
        logger.info("Schedule disabled, skipping", extra={"schedule_id": schedule_id})
        return

    user_id = schedule["user_id"]
    name = schedule["name"]
    task_message = schedule["task_message"]
    email = schedule["email"]

    augmented_message = f"[Scheduled Task: {name}]\nTask: {task_message}\nDeliver results via email to: {email}"

    try:
        result_text = _invoke_agent(augmented_message, user_id)
    except Exception as e:
        error_msg = str(e)
        logger.exception("Agent invocation failed", extra={"schedule_id": schedule_id})
        try:
            _update_last_run(user_id, schedule_id, "failed", error=error_msg)
            _write_result(schedule_id, user_id, "failed", error=error_msg)
        except Exception:
            logger.exception("Failed to record error result", extra={"schedule_id": schedule_id})
        metrics.add_metric(name="ErrorCount", unit=MetricUnit.Count, value=1)
        return

    # Agent succeeded — record results; don't re-raise to avoid duplicate retries
    try:
        _update_last_run(user_id, schedule_id, "success")
        _write_result(schedule_id, user_id, "success", result_summary=result_text[:500])
    except Exception:
        logger.exception("Failed to record success result", extra={"schedule_id": schedule_id})
    metrics.add_metric(name="SuccessCount", unit=MetricUnit.Count, value=1)
