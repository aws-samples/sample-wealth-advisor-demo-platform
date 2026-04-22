#!/usr/bin/env python3
"""Test Web Crawler MCP on AgentCore — using mcp SDK + httpx, no strands-agents.

Requires: boto3, mcp, httpx (drops strands-agents ~170MB).
Uses mcp SDK's ClientSession directly instead of Strands' MCPClient wrapper.
"""

import argparse
import asyncio
import hashlib
import json
import sys
from collections.abc import Generator
from typing import Any

import boto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class SigV4HTTPXAuth(httpx.Auth):
    """HTTPX auth handler that signs requests with SigV4 for bedrock-agentcore."""

    def __init__(self, credentials: Any, region: str):
        self.signer = SigV4Auth(credentials, "bedrock-agentcore", region)

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        headers = {k: v for k, v in request.headers.items() if k != "connection"}
        headers["x-amz-content-sha256"] = hashlib.sha256(request.content or b"").hexdigest()
        aws_req = AWSRequest(method=request.method, url=str(request.url), data=request.content, headers=headers)
        self.signer.add_auth(aws_req)
        request.headers.clear()
        request.headers.update(dict(aws_req.headers))
        yield request


def _build_url(arn, region):
    """Build the AgentCore MCP invocation URL."""
    encoded = arn.replace(":", "%3A").replace("/", "%2F")
    return f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded}/invocations?qualifier=DEFAULT"


async def main():
    parser = argparse.ArgumentParser(
        description="Test Web Crawler MCP on AgentCore — mcp SDK + httpx, no strands-agents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  ./scripts/test-web-crawler-mcp-sdk.sh arn:aws:bedrock-agentcore:us-west-2:123456:runtime/MyMcp --region us-west-2",
    )
    parser.add_argument("arn", help="AgentCore Runtime ARN for the Web Crawler MCP server")
    parser.add_argument("--region", default="us-west-2", help="AWS region (default: us-west-2)")
    args = parser.parse_args()

    url = _build_url(args.arn, args.region)
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    auth = SigV4HTTPXAuth(creds, args.region)

    # Connect via MCP streamable HTTP transport, then use ClientSession directly
    async with streamablehttp_client(url, auth=auth, timeout=900, terminate_on_close=False) as (read, write, _):
        async with ClientSession(read, write) as session:
            # Initialize handshake (handled by ClientSession)
            print("→ initialize")
            info = await session.initialize()
            # print(f"  server: {info.server_info}")

            # List available tools
            print("→ tools/list")
            tools = await session.list_tools()
            print(f"  tools: {[t.name for t in tools.tools]}")

            # # Call a lightweight read-only tool
            # print("→ tools/call get_recent_articles(hours=48, limit=5)")
            # result = await session.call_tool("get_recent_articles", {"hours": 48, "limit": 5})
            # tool_output = json.loads(result.content[0].text)
            # print(f"  success: {tool_output.get('success')}")
            # print(f"  articles: {tool_output.get('count', 0)}")
            # print(json.dumps(tool_output, indent=2)[:2000])

            # # Call save_articles_to_redshift (limited to 5 sources for testing)
            # print("→ tools/call save_articles_to_redshift(rss_only=True, max_sources=5)")
            # result = await session.call_tool("save_articles_to_redshift", {"rss_only": True})
            # tool_output = json.loads(result.content[0].text)
            # print(f"  success: {tool_output.get('success')}")
            # print(f"  articles_saved: {tool_output.get('articles_saved', 0)}")
            # print(f"  duplicates: {tool_output.get('duplicates', 0)}")
            # print(json.dumps(tool_output, indent=2)[:2000])

            # Call generate_general_themes
            print("→ tools/call generate_general_themes(hours=48, limit=6)")
            result = await session.call_tool("generate_general_themes", {"hours": 48, "limit": 6})
            tool_output = json.loads(result.content[0].text)
            print(f"  success: {tool_output.get('success')}")
            print(f"  themes_generated: {tool_output.get('themes_generated', 0)}")
            print(json.dumps(tool_output, indent=2)[:3000])


if __name__ == "__main__":
    asyncio.run(main())
