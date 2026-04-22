#!/usr/bin/env python3
"""
Local integration test that replicates the container environment exactly.

Starts the FastMCP server via mcp.run(transport="streamable-http") — the same
way the container runs — then calls generate_portfolio_themes_for_client over HTTP.
This catches event loop conflicts that unit tests with mocks cannot catch.

Requirements:
- PORTFOLIO_GATEWAY_URL must NOT be set (uses stdio client against local portfolio server)
- AWS credentials must be available (for Bedrock calls)

Usage:
  cd wealth-management-portal
  uv run python scripts/test-local-server-integration.py --client-id CL00005
  uv run python scripts/test-local-server-integration.py --client-id CL00005 --top-n 2 --themes-per-stock 1
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SERVER_PORT = 8099  # Use a non-conflicting port
SERVER_URL = f"http://localhost:{SERVER_PORT}/mcp"


def start_server(profile: str = None) -> subprocess.Popen:
    """Start the FastMCP HTTP server as a subprocess — same as the container CMD."""
    env = os.environ.copy()
    env["PORT"] = str(SERVER_PORT)
    # Ensure no Gateway URL — use local stdio portfolio server
    env.pop("PORTFOLIO_GATEWAY_URL", None)
    # Strip any hardcoded/expired credentials from .env so the profile is used
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        env.pop(key, None)
    if profile:
        env["AWS_PROFILE"] = profile

    logger.info("Starting FastMCP server on port %d (profile=%s)...", SERVER_PORT, profile or "default")
    proc = subprocess.Popen(
        ["uv", "run", "-m", "wealth_management_portal_web_crawler.web_crawler_mcp.http"],
        cwd=os.path.join(os.path.dirname(__file__), "..", "packages", "web_crawler"),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc


def wait_for_server(timeout: int = 30) -> bool:
    """Poll until the server is accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(f"http://localhost:{SERVER_PORT}/health", timeout=1)
            if resp.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


async def run_test(client_id: str, top_n: int, themes_per_stock: int, hours: int):
    logger.info("Connecting to local server at %s", SERVER_URL)

    async with streamablehttp_client(SERVER_URL, timeout=300, terminate_on_close=False) as (read, write, _):
        async with ClientSession(read, write) as mcp:
            await mcp.initialize()

            tools = await mcp.list_tools()
            tool_names = [t.name for t in tools.tools]
            logger.info("Available tools: %s", tool_names)

            if "generate_portfolio_themes_for_client" not in tool_names:
                logger.error("Tool not found — server may not have started correctly")
                return False

            logger.info(
                "Calling generate_portfolio_themes_for_client(client_id=%s, top_n=%d, themes_per_stock=%d)",
                client_id, top_n, themes_per_stock,
            )
            t0 = time.time()
            result = await mcp.call_tool(
                "generate_portfolio_themes_for_client",
                {
                    "client_id": client_id,
                    "top_n_stocks": top_n,
                    "themes_per_stock": themes_per_stock,
                    "hours": hours,
                },
            )
            elapsed = time.time() - t0

            raw = result.content[0].text
            try:
                output = json.loads(raw)
            except json.JSONDecodeError:
                logger.error("Non-JSON response: %s", raw)
                return False

            logger.info("--- Result (%.1fs) ---", elapsed)
            logger.info("success:          %s", output.get("success"))
            logger.info("themes_generated: %s", output.get("themes_generated", 0))
            logger.info("stocks_covered:   %s", output.get("stocks_covered", 0))

            if not output.get("success"):
                logger.error("FAILED: %s", output.get("error"))
                return False

            if output.get("error"):
                logger.error("error: %s", output["error"])

            print("\n--- Full response ---")
            print(json.dumps(output, indent=2))
            return True


def main():
    parser = argparse.ArgumentParser(description="Local container-equivalent integration test")
    parser.add_argument("--client-id", default="CL00005")
    parser.add_argument("--top-n", type=int, default=2, help="Top N stocks (keep small for local test)")
    parser.add_argument("--themes-per-stock", type=int, default=1)
    parser.add_argument("--hours", type=int, default=48)
    parser.add_argument("--profile", default=None, help="AWS profile name (e.g. wealth_management)")
    args = parser.parse_args()

    # Ensure no Gateway URL — use local portfolio server
    if "PORTFOLIO_GATEWAY_URL" in os.environ:
        logger.warning("PORTFOLIO_GATEWAY_URL is set — unsetting for local test to use stdio client")
        del os.environ["PORTFOLIO_GATEWAY_URL"]

    proc = start_server()

    try:
        logger.info("Waiting for server to be ready...")
        if not wait_for_server(timeout=30):
            # Print whatever the server output so far
            logger.error("Server did not start in time. Output:")
            if proc.stdout:
                print(proc.stdout.read())
            sys.exit(1)

        logger.info("Server is ready")
        success = asyncio.run(run_test(args.client_id, args.top_n, args.themes_per_stock, args.hours))
        sys.exit(0 if success else 1)

    finally:
        logger.info("Stopping server...")
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
