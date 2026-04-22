"""SSE streaming helpers for agent status updates to the UI."""

import json


def sse_event(event_type: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def status_event(message: str) -> str:
    """Agent is working — show status in UI."""
    return sse_event("status", {"message": message})


def token_event(text: str) -> str:
    """Streamed response token."""
    return sse_event("token", {"text": text})


def done_event(
    full_text: str, stock_data: dict | None = None, market_data: dict | None = None, sources: list | None = None
) -> str:
    """Final response — UI replaces streaming tokens with this."""
    payload: dict = {"message": full_text}
    if stock_data:
        payload["stockData"] = stock_data
    if market_data:
        payload["marketData"] = market_data
    if sources:
        payload["sources"] = sources
    return sse_event("done", payload)


def error_event(message: str) -> str:
    return sse_event("error", {"message": message})


def agent_start_event(agent: str) -> str:
    """A sub-agent has started processing."""
    return sse_event("agent_start", {"agent": agent})


def agent_end_event(agent: str) -> str:
    """A sub-agent has finished processing."""
    return sse_event("agent_end", {"agent": agent})
