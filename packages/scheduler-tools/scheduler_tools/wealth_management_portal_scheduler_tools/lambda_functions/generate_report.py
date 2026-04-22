import json
import os
import uuid

import boto3
import botocore.config
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()

# Global client variable for reuse across invocations
agentcore = None


def _get_agentcore_client():
    """Get or create the AgentCore client with proper timeout configuration."""
    global agentcore
    if agentcore is None:
        # Read timeout must exceed the longest expected report generation (~250s).
        # Lambda timeout is 300s, so use 290s to allow graceful error handling.
        agentcore = boto3.client(
            "bedrock-agentcore",
            config=botocore.config.Config(read_timeout=290),
        )
    return agentcore


def _invoke_report_agent(agent_arn: str, client_id: str) -> dict:
    """Invoke report agent via AgentCore SDK (handles SigV4 signing internally).

    Calls the report agent's FastAPI /invocations endpoint directly (not via MCP protocol).
    See scripts/test-report-invocation.py for the same pattern.
    """
    session_id = f"scheduler-{client_id}-{uuid.uuid4().hex}"
    payload = json.dumps({"client_id": client_id})

    client = _get_agentcore_client()
    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=session_id,
        payload=payload,
    )
    return json.loads(response["response"].read())


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Invoke report agent for a single client."""
    client_id = event.get("client_id")
    if not client_id:
        raise ValueError("client_id is required")

    logger.info(f"Generating report for client {client_id}")

    agent_arn = os.environ["REPORT_AGENT_ARN"]
    result = _invoke_report_agent(agent_arn, client_id)

    logger.info(f"Report generated: {result['report_id']}")

    return {
        "client_id": client_id,
        "report_id": result["report_id"],
        "s3_path": result["s3_path"],
        "status": result["status"],
    }
