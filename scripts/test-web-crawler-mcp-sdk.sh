#!/bin/bash
# Test Web Crawler MCP on AgentCore — using mcp SDK + httpx, no strands-agents
uv run --project packages/web_crawler python scripts/test-web-crawler-mcp-sdk.py "$@"
