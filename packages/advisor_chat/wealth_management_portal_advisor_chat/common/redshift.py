"""Redshift access via SmartChatDataAccess Gateway (production) with redshift_connector fallback for local dev."""

import json
import logging
import os
import re
import uuid

import boto3

logger = logging.getLogger(__name__)


def _convert_to_named(sql: str, params: list | None) -> tuple[str, list[str] | None]:
    """Convert %s placeholders to :p0,:p1 for the execute_sql tool."""
    if not params:
        return sql, None
    named = []
    idx = 0

    def replacer(_m):
        nonlocal idx
        named.append(str(params[idx]))
        name = f":p{idx}"
        idx += 1
        return name

    return re.sub(r"%s", replacer, sql), named


def execute_query(sql: str, params: list | None = None) -> list[dict]:
    """Execute SQL and return list of dicts."""
    if os.environ.get("REDSHIFT_HOST"):
        return _execute_local(sql, params)

    gateway_url = os.environ.get("SMART_CHAT_GATEWAY_URL")
    if gateway_url:
        return _execute_via_gateway(sql, params, gateway_url)

    # Legacy fallback: AgentCore MCP Runtime
    arn = os.environ["REDSHIFT_MCP_ARN"]
    region = os.environ.get("AWS_REGION", "us-west-2")
    creds = boto3.Session(region_name=region).get_credentials().get_frozen_credentials()

    from common_auth import SigV4HTTPXAuth
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp.mcp_client import MCPClient

    encoded_arn = arn.replace(":", "%3A").replace("/", "%2F")
    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            url,
            auth=SigV4HTTPXAuth(creds, region),
            timeout=120,
            terminate_on_close=False,
            headers={"X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": str(uuid.uuid4())},
        )
    )

    converted_sql, named_params = _convert_to_named(sql, params)
    tool_args = {"sql": converted_sql}
    if named_params:
        tool_args["params"] = named_params

    with mcp_client as client:
        result = client.call_tool_sync("execute_sql_001", "execute_sql", tool_args)

    data = json.loads(result["content"][0]["text"])
    if "error" in data:
        raise RuntimeError(f"Redshift MCP error: {data['error']}")
    return data.get("rows", [])


def _execute_via_gateway(sql: str, params: list | None, gateway_url: str) -> list[dict]:
    """Call SmartChatDataAccess Gateway (Lambda-backed MCP endpoint)."""
    from common_auth import SigV4HTTPXAuth
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp.mcp_client import MCPClient

    region = os.environ.get("AWS_REGION", "us-west-2")
    creds = boto3.Session(region_name=region).get_credentials().get_frozen_credentials()
    auth = SigV4HTTPXAuth(creds, region)

    mcp_client = MCPClient(lambda: streamablehttp_client(gateway_url, auth=auth, timeout=120, terminate_on_close=False))

    converted_sql, named_params = _convert_to_named(sql, params)
    tool_args = {"sql": converted_sql}
    if named_params:
        tool_args["params"] = named_params

    with mcp_client as client:
        # Gateway namespaces tool names — discover the full name first
        tools = client.list_tools_sync()
        tool_name = "execute_sql"
        for t in tools:
            if t.tool_name == "execute_sql" or t.tool_name.endswith("___execute_sql"):
                tool_name = t.tool_name
                break
        result = client.call_tool_sync("execute_sql_001", tool_name, tool_args)

    data = json.loads(result["content"][0]["text"])
    if "error" in data:
        raise RuntimeError(f"Redshift Gateway error: {data['error']}")
    return data.get("rows", [])


def _execute_local(sql: str, params: list | None = None) -> list[dict]:
    """Local dev fallback using redshift_connector via SSM tunnel."""
    import redshift_connector

    session = boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE"),
        region_name=os.environ.get("AWS_REGION", "us-west-2"),
    )
    creds = session.client("redshift-serverless").get_credentials(
        workgroupName=os.environ.get("REDSHIFT_WORKGROUP", "financial-advisor-wg")
    )
    conn = redshift_connector.connect(
        host=os.environ["REDSHIFT_HOST"],
        port=int(os.environ.get("REDSHIFT_PORT", "5439")),
        user=creds["dbUser"],
        password=creds["dbPassword"],
        database=os.environ.get("REDSHIFT_DATABASE", "financial-advisor-db"),
        ssl=True,
        sslmode="require",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    finally:
        conn.close()
