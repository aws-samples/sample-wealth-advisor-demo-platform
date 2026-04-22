"""Graph Search Agent — Strands Agent for Neptune Analytics AI search.

Deployed on Bedrock AgentCore. Uses Neptune MCP server via AgentCore gateway
for graph queries, and Bedrock for Cypher generation + reasoning.
"""

import json
import logging
import os
import uuid

from wealth_management_portal_neptune_analytics_core import get_neptune_client

from ..config import is_agentcore

logger = logging.getLogger(__name__)


def _get_neptune_mcp_tool_client():
    """Get MCP client to Neptune Analytics Gateway."""
    gateway_url = os.environ.get("NEPTUNE_GATEWAY_URL", "")
    if not gateway_url:
        raise ValueError("NEPTUNE_GATEWAY_URL not set")
    import boto3
    from common_auth import SigV4HTTPXAuth
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp.mcp_client import MCPClient

    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    region = os.environ.get("AWS_REGION", "us-west-2")
    return MCPClient(
        lambda: streamablehttp_client(
            gateway_url,
            auth=SigV4HTTPXAuth(credentials, region),
            timeout=120,
            terminate_on_close=False,
        )
    )


def _extract_mcp_result(result: dict) -> dict:
    """Extract parsed result from an MCP tool call response.
    Step 1: error check. Step 2: Gateway structuredContent. Step 3: local MCP fallback.
    """
    if result.get("status") == "error":
        raise RuntimeError(f"MCP tool error: {result}")
    structured = result.get("structuredContent")
    if structured:
        return structured
    content = result.get("content", [])
    if content and isinstance(content[0], dict) and "text" in content[0]:
        return json.loads(content[0]["text"])
    return {}


def build_tool_name_map(client, short_names: list[str]) -> dict[str, str]:
    """Map short tool names to Gateway-prefixed full names.
    Gateway prefixes tool names: {targetLogicalId}___toolName.
    Falls back to short names for local dev (no prefix).
    """
    try:
        tools = client.list_tools_sync()
        full_names = [t.tool_name for t in tools]
        name_map = {}
        for short in short_names:
            match = next((f for f in full_names if f.endswith(f"___{short}") or f == short), short)
            name_map[short] = match
        return name_map
    except Exception:
        return {n: n for n in short_names}


_TOOL_NAMES = ["execute_cypher", "test_connection", "find_similar_clients", "compute_degree_centrality"]


class NeptuneMCPQueryClient:
    """Wraps AgentCore Gateway MCP client to match NeptuneAnalyticsClient interface."""

    def __init__(self):
        self._cached_client = None
        self._name_map: dict[str, str] | None = None

    def _get_or_create_client(self):
        if self._cached_client is None:
            self._cached_client = _get_neptune_mcp_tool_client()
        return self._cached_client

    def _reset_client(self):
        self._cached_client = None
        self._name_map = None

    def _get_name_map(self, client) -> dict[str, str]:
        if self._name_map is None:
            self._name_map = build_tool_name_map(client, _TOOL_NAMES)
        return self._name_map

    def execute_query(self, query: str) -> dict:
        try:
            with self._get_or_create_client() as client:
                name_map = self._get_name_map(client)
                result = client.call_tool_sync(str(uuid.uuid4()), name_map["execute_cypher"], {"query": query})
            return _extract_mcp_result(result) or {"results": []}
        except Exception:
            self._reset_client()
            raise

    def test_connection(self) -> bool:
        try:
            with self._get_or_create_client() as client:
                name_map = self._get_name_map(client)
                result = client.call_tool_sync(str(uuid.uuid4()), name_map["test_connection"], {})
            return _extract_mcp_result(result).get("connected", False)
        except Exception as e:
            logger.warning("MCP test_connection failed: %s", e)
            self._reset_client()
            return False


def _get_query_client():
    """Get Neptune query client — MCP via AgentCore Gateway if available, else direct boto3."""
    if is_agentcore() and os.environ.get("NEPTUNE_GATEWAY_URL"):
        try:
            client = NeptuneMCPQueryClient()
            if client.test_connection():
                logger.info("Using Neptune MCP client via AgentCore Gateway")
                return client
            logger.warning("MCP test_connection returned False, falling back to direct boto3")
        except Exception as e:
            logger.warning("AgentCore Gateway MCP unavailable: %s", e)
    return get_neptune_client()
