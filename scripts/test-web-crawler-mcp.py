#!/usr/bin/env python3
"""Test Web Crawler MCP on AgentCore — raw HTTP + SigV4, zero mcp/strands/httpx deps.

Only requires: boto3 (botocore for SigV4) + requests (for HTTP).
Proves MCP servers can be invoked without the heavy strands-agents (~170MB) dependency.
"""

import argparse
import hashlib
import json
import sys
import uuid

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


def _build_url(arn, region):
    """Build the AgentCore MCP invocation URL."""
    encoded = arn.replace(":", "%3A").replace("/", "%2F")
    return f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded}/invocations?qualifier=DEFAULT"


def _signed_post(url, payload, region, creds, extra_headers=None):
    """Sign and send a JSON-RPC request to AgentCore with SigV4."""
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "x-amz-content-sha256": hashlib.sha256(body).hexdigest(),
        **(extra_headers or {}),
    }
    aws_req = AWSRequest(method="POST", url=url, data=body, headers=headers)
    SigV4Auth(creds, "bedrock-agentcore", region).add_auth(aws_req)

    resp = requests.post(url, data=body, headers=dict(aws_req.headers), timeout=120)
    resp.raise_for_status()
    return resp


def _parse_response(resp):
    """Extract JSON-RPC result from direct JSON or SSE response."""
    if "text/event-stream" in resp.headers.get("content-type", ""):
        # SSE: find last data line with a result
        for line in reversed(resp.text.strip().split("\n")):
            if line.startswith("data: "):
                msg = json.loads(line[6:])
                if "result" in msg or "error" in msg:
                    return msg
        raise ValueError(f"No JSON-RPC result in SSE:\n{resp.text[:500]}")
    return resp.json()


def main():
    parser = argparse.ArgumentParser(
        description="Test Web Crawler MCP on AgentCore — raw HTTP + SigV4, zero mcp/strands/httpx deps.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  ./scripts/test-web-crawler-mcp.sh arn:aws:bedrock-agentcore:us-west-2:123456:runtime/MyMcp --region us-west-2",
    )
    parser.add_argument("arn", help="AgentCore Runtime ARN for the Web Crawler MCP server")
    parser.add_argument("--region", default="us-west-2", help="AWS region (default: us-west-2)")
    args = parser.parse_args()

    url = _build_url(args.arn, args.region)
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    session_headers = {
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": f"test-session-{uuid.uuid4()}",
    }

    # Step 1: MCP initialize handshake
    print("→ initialize")
    resp = _signed_post(url, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-script", "version": "1.0"},
        },
    }, args.region, creds, session_headers)
    init = _parse_response(resp)
    if "error" in init:
        print(f"  ERROR: {init['error']}")
        sys.exit(1)
    print(f"  server: {init['result']['serverInfo']}")

    # Capture MCP session ID for subsequent requests
    mcp_sid = resp.headers.get("Mcp-Session-Id")
    if mcp_sid:
        session_headers["Mcp-Session-Id"] = mcp_sid

    # Step 2: Send initialized notification
    print("→ initialized")
    _signed_post(url, {
        "jsonrpc": "2.0", "method": "notifications/initialized",
    }, args.region, creds, session_headers)

    # Step 3: Call a lightweight read-only tool
    print("→ tools/call get_recent_articles(hours=48, limit=5)")
    resp = _signed_post(url, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "get_recent_articles", "arguments": {"hours": 48, "limit": 5}},
    }, args.region, creds, session_headers)
    result = _parse_response(resp)
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        sys.exit(1)

    tool_output = json.loads(result["result"]["content"][0]["text"])
    print(f"  success: {tool_output.get('success')}")
    print(f"  articles: {tool_output.get('count', 0)}")
    print(json.dumps(tool_output, indent=2)[:2000])


if __name__ == "__main__":
    main()
