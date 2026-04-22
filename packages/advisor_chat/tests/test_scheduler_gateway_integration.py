"""Integration tests for Scheduler and Email Sender MCP gateway connections.

These tests verify the routing agent can discover and list tools from both gateways.
They are skipped when the gateway URLs are not set (i.e. outside of a deployed environment).
"""

import os

import pytest

SCHEDULER_GATEWAY_URL = os.environ.get("SCHEDULER_GATEWAY_URL")
EMAIL_SENDER_GATEWAY_URL = os.environ.get("EMAIL_SENDER_GATEWAY_URL")


@pytest.mark.skipif(not SCHEDULER_GATEWAY_URL, reason="SCHEDULER_GATEWAY_URL not set")
def test_scheduler_gateway_lists_tools():
    """Agent can discover tools from the Scheduler MCP Gateway."""
    import boto3
    from common_auth import SigV4HTTPXAuth
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp.mcp_client import MCPClient

    region = os.environ.get("AWS_REGION", "us-west-2")
    creds = boto3.Session(region_name=region).get_credentials().get_frozen_credentials()
    auth = SigV4HTTPXAuth(creds, region)

    mcp_client = MCPClient(
        lambda: streamablehttp_client(SCHEDULER_GATEWAY_URL, auth=auth, timeout=120, terminate_on_close=False)
    )

    with mcp_client as client:
        tools = client.list_tools_sync()

    tool_names = [t.tool_name for t in tools]
    assert any("create_schedule" in name for name in tool_names), f"create_schedule not found in {tool_names}"
    assert any("list_schedules" in name for name in tool_names), f"list_schedules not found in {tool_names}"
    assert any("delete_schedule" in name for name in tool_names), f"delete_schedule not found in {tool_names}"
    assert any("toggle_schedule" in name for name in tool_names), f"toggle_schedule not found in {tool_names}"


@pytest.mark.skipif(not EMAIL_SENDER_GATEWAY_URL, reason="EMAIL_SENDER_GATEWAY_URL not set")
def test_email_sender_gateway_lists_tools():
    """Agent can discover tools from the Email Sender MCP Gateway."""
    import boto3
    from common_auth import SigV4HTTPXAuth
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp.mcp_client import MCPClient

    region = os.environ.get("AWS_REGION", "us-west-2")
    creds = boto3.Session(region_name=region).get_credentials().get_frozen_credentials()
    auth = SigV4HTTPXAuth(creds, region)

    mcp_client = MCPClient(
        lambda: streamablehttp_client(EMAIL_SENDER_GATEWAY_URL, auth=auth, timeout=120, terminate_on_close=False)
    )

    with mcp_client as client:
        tools = client.list_tools_sync()

    tool_names = [t.tool_name for t in tools]
    assert any("send_email" in name for name in tool_names), f"send_email not found in {tool_names}"
