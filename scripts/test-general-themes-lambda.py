#!/usr/bin/env python3
"""Local test for generate_general_themes lambda logic.

Simulates exactly what the lambda does: MCP handshake → save_articles_to_redshift → generate_general_themes.
Only requires: boto3 + requests (same deps as the lambda).

Usage:
  AWS_PROFILE=wealth_management python scripts/test-general-themes-lambda.py \
    arn:aws:bedrock-agentcore:us-west-2:507139572291:runtime/wealthmanagementionWebCrawlerMcpBFEAD281-2iGk6CG7c5
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


def _build_url(arn: str, region: str) -> str:
    encoded = arn.replace(":", "%3A").replace("/", "%2F")
    return f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded}/invocations?qualifier=DEFAULT"


def _signed_post(url: str, payload: dict, region: str, creds, session_headers: dict) -> requests.Response:
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "x-amz-content-sha256": hashlib.sha256(body).hexdigest(),
        **session_headers,
    }
    aws_req = AWSRequest(method="POST", url=url, data=body, headers=headers)
    SigV4Auth(creds, "bedrock-agentcore", region).add_auth(aws_req)
    resp = requests.post(url, data=body, headers=dict(aws_req.headers), timeout=900)
    resp.raise_for_status()
    return resp


def _parse_response(resp: requests.Response) -> dict:
    if "text/event-stream" in resp.headers.get("content-type", ""):
        for line in reversed(resp.text.strip().split("\n")):
            if line.startswith("data: "):
                msg = json.loads(line[6:])
                if "result" in msg or "error" in msg:
                    return msg
        raise ValueError(f"No JSON-RPC result in SSE stream:\n{resp.text[:500]}")
    return resp.json()


def _call_mcp_tool(url: str, tool_name: str, arguments: dict, region: str, creds) -> dict:
    session_headers = {
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": f"local-test-{uuid.uuid4()}",
    }

    # 1. initialize
    print(f"  → initialize")
    resp = _signed_post(url, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "scheduler-lambda", "version": "1.0"},
        },
    }, region, creds, session_headers)
    init = _parse_response(resp)
    if "error" in init:
        raise RuntimeError(f"MCP initialize failed: {init['error']}")
    print(f"  ✓ server: {init['result']['serverInfo']}")

    mcp_sid = resp.headers.get("Mcp-Session-Id")
    if mcp_sid:
        session_headers["Mcp-Session-Id"] = mcp_sid

    # 2. initialized notification
    print(f"  → notifications/initialized")
    _signed_post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"},
                 region, creds, session_headers)

    # 3. tools/call
    print(f"  → tools/call {tool_name}({arguments})")
    resp = _signed_post(url, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }, region, creds, session_headers)
    result = _parse_response(resp)
    if "error" in result:
        raise RuntimeError(f"MCP tool '{tool_name}' failed: {result['error']}")

    return json.loads(result["result"]["content"][0]["text"])


def main():
    parser = argparse.ArgumentParser(description="Local test for generate_general_themes lambda logic")
    parser.add_argument("arn", help="Web Crawler MCP AgentCore Runtime ARN")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--hours", type=int, default=48)
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--skip-crawl", action="store_true", help="Skip save_articles_to_redshift, only test theme generation")
    args = parser.parse_args()

    url = _build_url(args.arn, args.region)
    creds = boto3.Session().get_credentials().get_frozen_credentials()

    # Step 1: crawl
    if not args.skip_crawl:
        print("\n[Step 1] save_articles_to_redshift (rss_only=True)")
        crawl_data = _call_mcp_tool(url, "save_articles_to_redshift", {"rss_only": True}, args.region, creds)
        print(f"  articles_saved: {crawl_data.get('articles_saved', 0)}")
        print(f"  duplicates:     {crawl_data.get('duplicates', 0)}")
        print(f"  success:        {crawl_data.get('success')}")
        if not crawl_data.get("success"):
            print(f"  WARNING: {crawl_data.get('error')} — continuing anyway")
    else:
        print("\n[Step 1] Skipped (--skip-crawl)")

    # Step 2: generate themes
    print(f"\n[Step 2] generate_general_themes (hours={args.hours}, limit={args.limit})")
    result = _call_mcp_tool(url, "generate_general_themes", {"hours": args.hours, "limit": args.limit}, args.region, creds)
    print(f"  success:          {result.get('success')}")
    print(f"  themes_generated: {result.get('themes_generated', 0)}")
    print(f"  message:          {result.get('message')}")
    if not result.get("success"):
        print(f"  ERROR: {result.get('error')}")
        sys.exit(1)

    print("\n✓ Lambda logic test passed")


if __name__ == "__main__":
    main()
