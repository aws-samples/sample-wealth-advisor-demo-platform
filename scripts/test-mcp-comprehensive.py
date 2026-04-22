#!/usr/bin/env python3
"""Test deployed Portfolio Data Server via AgentCore Gateway.

Uses mcp SDK + httpx + SigV4 to call the deployed Gateway,
validating network connectivity and tool execution end-to-end.
"""
import argparse
import asyncio
import hashlib
import json
import os
import signal
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


def discover_gateway_url(cfn, agentcore_ctrl, stack_name: str) -> str:
    """Find the Portfolio Data Gateway URL from stack resources."""
    paginator = cfn.get_paginator("list_stack_resources")
    for page in paginator.paginate(StackName=stack_name):
        for r in page["StackResourceSummaries"]:
            if r["ResourceType"] == "AWS::BedrockAgentCore::Gateway" and "PortfolioGateway" in r["LogicalResourceId"]:
                gateway_id = r["PhysicalResourceId"]
                resp = agentcore_ctrl.get_gateway(gatewayIdentifier=gateway_id)
                return resp["gatewayUrl"]
    raise RuntimeError(f"No PortfolioGateway found in stack {stack_name}")


async def test_mcp_tools(gateway_url: str, region: str):
    """Test all MCP tools via the deployed AgentCore Gateway."""
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    auth = SigV4HTTPXAuth(creds, region)

    async with streamablehttp_client(gateway_url, auth=auth, timeout=120, terminate_on_close=False) as (read, write, _):
        async with ClientSession(read, write) as session:
            print("\n→ initialize")
            await session.initialize()

            print("→ tools/list")
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            print(f"  tools ({len(tool_names)}): {tool_names}")

            # Gateway prefixes tool names with target ID, e.g. "...LambdaTarget___list_clients"
            # Build a lookup: short_name -> full_name
            def resolve(short_name: str) -> str:
                for name in tool_names:
                    if name.endswith(f"___{short_name}"):
                        return name
                return short_name

            # Test 1: list_clients
            print("\n" + "=" * 20 + " list_clients " + "=" * 20)
            result = await session.call_tool(resolve("list_clients"), {})
            data = json.loads(result.content[0].text)
            print(f"✓ list_clients: {len(data)} clients")
            for c in data[:3]:
                print(f"  • {c['client_id']}: {c['first_name']} {c['last_name']} ({c['segment']})")

            # Test 2: get_client_report_data
            print("\n" + "=" * 15 + " get_client_report_data " + "=" * 15)
            result = await session.call_tool(resolve("get_client_report_data"), {"client_id": "CL00014"})
            data = json.loads(result.content[0].text)
            print(f"✓ get_client_report_data: {len(data)} sections")
            for key, value in data.items():
                if isinstance(value, list):
                    print(f"  • {key}: {len(value)} records")
                elif isinstance(value, dict):
                    print(f"  • {key}: {len(value)} fields")

            # Test 3: save_report
            print("\n" + "=" * 20 + " save_report " + "=" * 20)
            result = await session.call_tool(resolve("save_report"), {
                "report_id": "RPT001",
                "client_id": "CL00014",
                "s3_path": "s3://test-bucket/test.pdf",
                "generated_date": "2024-01-15T10:30:00Z",
                "status": "completed",
            })
            data = json.loads(result.content[0].text)
            print(f"✓ save_report: {data}")

    print("\n" + "=" * 60)
    print("🎉 Portfolio Data Gateway is working!")


def main():
    parser = argparse.ArgumentParser(description="Test deployed Portfolio Data Server via AgentCore Gateway")
    parser.add_argument("--stack-name", default="wealth-management-portal-infra-sandbox-Application")
    parser.add_argument("--gateway-url", default=None, help="Override auto-discovered Gateway URL")
    args = parser.parse_args()

    # Hard 90s timeout
    def timeout_handler(signum, frame):
        print("\n❌ Timed out after 90s — Gateway unreachable or hanging")
        os._exit(1)
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(90)

    print("Portfolio Data Server - Gateway Test")
    print("=" * 60)

    region = boto3.session.Session().region_name or "us-west-2"

    if args.gateway_url:
        gateway_url = args.gateway_url
    else:
        cfn = boto3.client("cloudformation", region_name=region)
        agentcore_ctrl = boto3.client("bedrock-agentcore-control", region_name=region)
        gateway_url = discover_gateway_url(cfn, agentcore_ctrl, args.stack_name)

    print(f"  Gateway URL: {gateway_url}")

    try:
        asyncio.run(test_mcp_tools(gateway_url, region))
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    signal.alarm(0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
