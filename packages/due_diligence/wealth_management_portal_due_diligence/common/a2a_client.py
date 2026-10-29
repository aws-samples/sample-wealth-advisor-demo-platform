"""A2A client — calls agent endpoints via AgentCore (deployed) or HTTP localhost (dev)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_LOCAL_PORTS: dict[str, int] = {
    "dd-supervisor": 8086,
    "evidence-gatherer": 8087,
    "framework-assessor": 8088,
    "quant-analyst": 8089,
    "report-drafter": 8090,
    "qa-agent": 8091,
}

_ENV_KEYS: dict[str, str] = {
    "dd-supervisor": "DD_SUPERVISOR_ENDPOINT",
    "evidence-gatherer": "EVIDENCE_GATHERER_ENDPOINT",
    "framework-assessor": "FRAMEWORK_ASSESSOR_ENDPOINT",
    "quant-analyst": "QUANT_ANALYST_ENDPOINT",
    "report-drafter": "REPORT_DRAFTER_ENDPOINT",
    "qa-agent": "QA_AGENT_ENDPOINT",
}

# ARN env vars — when set, use AgentCore SDK instead of HTTP
_ARN_KEYS: dict[str, str] = {
    "dd-supervisor": "DD_SUPERVISOR_ARN",
    "evidence-gatherer": "EVIDENCE_GATHERER_ARN",
    "framework-assessor": "FRAMEWORK_ASSESSOR_ARN",
    "quant-analyst": "QUANT_ANALYST_ARN",
    "report-drafter": "REPORT_DRAFTER_ARN",
    "qa-agent": "QA_AGENT_ARN",
}


def get_agent_endpoint(agent_name: str) -> str:
    """Return the endpoint URL or ARN for an agent."""
    # Check for ARN first (deployed mode via AgentCore)
    arn_key = _ARN_KEYS.get(agent_name)
    if arn_key:
        arn = os.environ.get(arn_key)
        if arn:
            return arn

    # Check for URL override
    env_key = _ENV_KEYS.get(agent_name)
    if env_key:
        override = os.environ.get(env_key)
        if override:
            return override

    # Local dev fallback
    port = _LOCAL_PORTS[agent_name]
    return f"http://localhost:{port}"


async def invoke_agent(endpoint: str, payload_json: str, timeout: float = 120.0) -> Any:
    """Invoke an agent — routes to AgentCore SDK if endpoint is an ARN, else HTTP POST."""
    if endpoint.startswith("arn:"):
        return await _invoke_via_agentcore(endpoint, payload_json)
    return await _invoke_via_http(endpoint, payload_json, timeout)


async def _invoke_via_http(endpoint: str, payload_json: str, timeout: float = 120.0) -> Any:
    """POST payload to agent /invocations, return parsed JSON."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{endpoint}/invocations",
            content=payload_json,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()


async def _invoke_via_agentcore(agent_arn: str, payload_json: str) -> Any:
    """Invoke an AgentCore Runtime agent by ARN."""
    import uuid

    import boto3
    import botocore.config

    client = boto3.client(
        "bedrock-agentcore",
        config=botocore.config.Config(read_timeout=290),
    )
    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=f"dd-{uuid.uuid4().hex}",
        payload=payload_json.encode("utf-8") if isinstance(payload_json, str) else payload_json,
    )
    response_body = response["response"].read().decode("utf-8")
    return json.loads(response_body)
