"""Runtime configuration for local vs AgentCore deployment."""

import os


def is_agentcore() -> bool:
    """Return True if running in AgentCore mode."""
    return os.environ.get("GRAPH_SEARCH_MODE", "local").lower() == "agentcore"
