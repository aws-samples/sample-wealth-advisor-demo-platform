"""Helper to get Portfolio Data MCP client for accessing Redshift."""

import json
import os

import boto3
from common_auth import SigV4HTTPXAuth
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient


def build_tool_name_map(client, short_names: list[str]) -> dict[str, str]:
    """Resolve short tool names to full Gateway-prefixed names (cached per session).

    The AgentCore Gateway prefixes tool names with the CDK target logical ID
    (e.g. ``LambdaTarget5F219D6D___get_recent_articles``).  This helper maps
    each *short_name* to its full prefixed name so that ``call_tool_sync`` sends
    the name the Gateway expects.  If no prefixed match is found the short name
    is returned as-is (works for stdio / local dev).
    """
    tools = client.list_tools_sync()
    mapping: dict[str, str] = {}
    for short in short_names:
        for t in tools:
            if t.tool_name == short or t.tool_name.endswith(f"___{short}"):
                mapping[short] = t.tool_name
                break
        else:
            mapping[short] = short
    return mapping


def get_portfolio_mcp_client() -> MCPClient:
    """Get MCP client for Portfolio Data Access based on environment configuration."""
    gateway_url = os.getenv("PORTFOLIO_GATEWAY_URL")

    if gateway_url:
        # Use streamable HTTP client with SigV4 auth via Gateway (production)
        credentials = boto3.Session().get_credentials().get_frozen_credentials()
        region = os.getenv("AWS_REGION", "us-east-1")
        auth = SigV4HTTPXAuth(credentials, region)
        return MCPClient(lambda: streamablehttp_client(gateway_url, auth=auth, timeout=120, terminate_on_close=False))
    else:
        raise ValueError("PORTFOLIO_GATEWAY_URL environment variable is required")


def extract_mcp_data(result: dict) -> dict:
    """Extract data from MCP tool call result.

    Handles both Gateway (structuredContent) and direct MCP (content[0]['text']) formats.
    """
    if result.get("status") == "error":
        error_text = ""
        for item in result.get("content", []):
            if isinstance(item, dict) and item.get("text"):
                error_text += item["text"]
        raise RuntimeError(f"MCP tool error: {error_text or result}")
    if "structuredContent" in result and result["structuredContent"] is not None:
        return result["structuredContent"]
    content = result.get("content", [])
    if content and isinstance(content[0], dict) and content[0].get("text"):
        return json.loads(content[0]["text"])
    return {}
