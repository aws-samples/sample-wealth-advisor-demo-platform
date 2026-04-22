#!/bin/bash
# Test Web Crawler MCP on AgentCore — raw HTTP, zero mcp/strands deps
uv run --project packages/api python scripts/test-web-crawler-mcp.py "$@"
