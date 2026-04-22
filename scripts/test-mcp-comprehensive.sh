#!/bin/bash
# Test Portfolio Data Server via AgentCore Gateway — mcp SDK + httpx + SigV4
uv run --project packages/report python scripts/test-mcp-comprehensive.py "$@"