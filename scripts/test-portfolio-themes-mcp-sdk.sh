#!/bin/bash
# Test portfolio themes generation via Web Crawler MCP on AgentCore — using mcp SDK + httpx
uv run --project packages/scheduler-tools python scripts/test-portfolio-themes-mcp-sdk.py "$@"
