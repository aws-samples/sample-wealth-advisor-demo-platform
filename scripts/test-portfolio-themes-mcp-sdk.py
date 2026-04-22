#!/usr/bin/env python3
"""Test Portfolio Data Access MCP — invoke generate_portfolio_themes_for_client.

Uses mcp SDK + httpx + SigV4HTTPXAuth (same transport as test-web-crawler-mcp-sdk.py).
Requires: boto3, mcp, httpx

Usage:
  python scripts/test-portfolio-themes-mcp-sdk.py <WEB_CRAWLER_MCP_ARN> --client-id CL00001
  python scripts/test-portfolio-themes-mcp-sdk.py <ARN> --client-id CL00001 --top-n 3 --themes-per-stock 2 --hours 24
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


def _build_url(arn: str, region: str) -> str:
    encoded = arn.replace(":", "%3A").replace("/", "%2F")
    return f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded}/invocations?qualifier=DEFAULT"


async def main():
    parser = argparse.ArgumentParser(
        description="Invoke generate_portfolio_themes_for_client via Web Crawler MCP on AgentCore.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python scripts/test-portfolio-themes-mcp-sdk.py \\\n"
            "    arn:aws:bedrock-agentcore:us-west-2:507139572291:runtime/wealthmanagementionWebCrawlerMcpBFEAD281-2iGk6CG7c5 \\\n"
            "    --client-id CL00001"
        ),
    )
    parser.add_argument("arn", help="AgentCore Runtime ARN for the Web Crawler MCP server")
    parser.add_argument("--client-id", required=True, help="Client ID to generate portfolio themes for (e.g. CL00001)")
    parser.add_argument("--top-n", type=int, default=5, help="Top N stocks to analyse (default: 5)")
    parser.add_argument("--themes-per-stock", type=int, default=2, help="Themes to generate per stock (default: 2)")
    parser.add_argument("--hours", type=int, default=48, help="Lookback window in hours for articles (default: 48)")
    parser.add_argument("--region", default="us-west-2", help="AWS region (default: us-west-2)")
    parser.add_argument("--profile", default=None, help="AWS profile name (default: env/instance credentials)")
    args = parser.parse_args()

    url = _build_url(args.arn, args.region)
    session_kwargs = {"profile_name": args.profile} if args.profile else {}
    creds = boto3.Session(**session_kwargs).get_credentials().get_frozen_credentials()
    auth = SigV4HTTPXAuth(creds, args.region)

    print(f"→ Connecting to: {args.arn}")
    print(f"→ Client ID:     {args.client_id}")
    print(f"→ Parameters:    top_n_stocks={args.top_n}, themes_per_stock={args.themes_per_stock}, hours={args.hours}")

    async with streamablehttp_client(url, auth=auth, timeout=900, terminate_on_close=False) as (read, write, _):
        async with ClientSession(read, write) as mcp:
            print("\n→ initialize")
            await mcp.initialize()

            print("→ tools/list")
            tools = await mcp.list_tools()
            tool_names = [t.name for t in tools.tools]
            print(f"  tools: {tool_names}")

            if "generate_portfolio_themes_for_client" not in tool_names:
                print("  ERROR: tool 'generate_portfolio_themes_for_client' not found on this MCP server", file=sys.stderr)
                sys.exit(1)

            print(f"\n→ tools/call generate_portfolio_themes_for_client(client_id={args.client_id!r}, ...)")
            result = await mcp.call_tool(
                "generate_portfolio_themes_for_client",
                {
                    "client_id": args.client_id,
                    "top_n_stocks": args.top_n,
                    "themes_per_stock": args.themes_per_stock,
                    "hours": args.hours,
                },
            )

            raw = result.content[0].text
            try:
                output = json.loads(raw)
            except json.JSONDecodeError:
                print(f"  raw response:\n{raw}")
                sys.exit(1)

            print(f"  success:          {output.get('success')}")
            print(f"  themes_generated: {output.get('themes_generated', 0)}")
            print(f"  stocks_covered:   {output.get('stocks_covered', 0)}")
            if output.get("error"):
                print(f"  error:            {output['error']}", file=sys.stderr)

            print("\n--- Full response ---")
            print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
