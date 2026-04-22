# Data-fetch and save helpers for the report agent.
# Uses the Strands MCP client to talk to the Portfolio Data Server, and a direct
# Bedrock call for Next Best Action generation. Narrative generation lives in agent.py.
import json
import logging
import os
from dataclasses import dataclass
from datetime import date

import boto3
from common_auth import SigV4HTTPXAuth
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

from ..generator import ReportGenerator
from ..models import ClientProfile, Communications, Portfolio
from ..prompts import NEXT_BEST_ACTION_PROMPT
from ..transformers import build_client_profile, build_communications, build_market_context, build_portfolio

logger = logging.getLogger(__name__)


@dataclass
class ReportData:
    """Typed container for fetched report data, keeping models separate from rendered components."""

    components: dict  # deterministic_sections, synthesis_prompts, chart_svgs
    profile: ClientProfile
    portfolio: Portfolio
    communications: Communications


def generate_next_best_action(report_data: ReportData) -> str | None:
    """Generate a Next Best Action recommendation via a direct Bedrock call.

    Returns the NBA string (max 1000 chars), or None on failure.
    """
    prompt = NEXT_BEST_ACTION_PROMPT.format(
        profile_json=report_data.profile.model_dump_json(indent=2),
        portfolio_json=report_data.portfolio.model_dump_json(indent=2),
        communications_json=report_data.communications.model_dump_json(indent=2),
    )
    bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    model_id = os.environ["REPORT_BEDROCK_MODEL_ID"]
    response = bedrock.invoke_model(
        modelId=model_id,
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 256,
                "messages": [{"role": "user", "content": prompt}],
            }
        ),
    )
    nba_text = json.loads(response["body"].read())["content"][0]["text"].strip()
    # Truncate to VARCHAR(1000) limit to prevent Redshift INSERT errors
    return nba_text[:1000] if nba_text else None


def _extract_mcp_data(result: dict) -> dict | list:
    """Extract parsed data from an MCPToolResult, handling structuredContent and text content."""
    if result.get("status") == "error":
        content = result.get("content", [])
        msg = content[0]["text"] if content and content[0].get("text") else "Unknown MCP error"
        logger.error("MCP tool call failed: %s", msg)
        raise RuntimeError(f"MCP tool call failed: {msg}")

    # Prefer structuredContent (returned by Bedrock AgentCore Gateway)
    if "structuredContent" in result and result["structuredContent"]:
        return result["structuredContent"]

    # Fall back to text content
    logger.info("_extract_mcp_data: falling back from structuredContent to content[0]['text']")
    content = result.get("content", [])
    if not content:
        raise RuntimeError(f"MCP tool returned empty content. Result keys: {list(result.keys())}")

    text = content[0].get("text", "")
    if not text:
        raise RuntimeError(
            f"MCP tool returned empty text. Content item keys: {list(content[0].keys())}. "
            f"Result keys: {list(result.keys())}"
        )

    return json.loads(text)


def _build_tool_name_map(client, short_names: list[str]) -> dict[str, str]:
    """Resolve short tool names to full Gateway-prefixed names."""
    tools = client.list_tools_sync()
    logger.info("_build_tool_name_map: list_tools_sync returned %d tools", len(tools))
    mapping: dict[str, str] = {}
    for short in short_names:
        for t in tools:
            if t.tool_name == short or t.tool_name.endswith(f"___{short}"):
                mapping[short] = t.tool_name
                break
        else:
            # Log available tool names to aid debugging
            available = [t.tool_name for t in tools]
            logger.warning(
                "_build_tool_name_map: tool '%s' not found in %d tools: %s. Using short name as fallback.",
                short,
                len(available),
                available,
            )
            mapping[short] = short
    logger.info("_build_tool_name_map resolved: %s", mapping)
    return mapping


def _get_mcp_client() -> MCPClient:
    """Get MCP client based on environment configuration."""
    gateway_url = os.getenv("PORTFOLIO_GATEWAY_URL")

    if gateway_url:
        # Use streamable HTTP client with SigV4 auth via Gateway
        credentials = boto3.Session().get_credentials().get_frozen_credentials()
        region = os.getenv("AWS_REGION", "us-east-1")
        auth = SigV4HTTPXAuth(credentials, region)
        return MCPClient(lambda: streamablehttp_client(gateway_url, auth=auth, timeout=120, terminate_on_close=False))
    else:
        raise ValueError("PORTFOLIO_GATEWAY_URL environment variable is required")


def fetch_report_data(client_id: str, mcp_client=None) -> ReportData:
    """
    Fetch and generate client briefing report data.

    Args:
        client_id: Redshift client ID (e.g., "CLT-001").
        mcp_client: Optional pre-initialized MCP client. If provided, caller manages lifecycle.

    Returns:
        ReportData with components (deterministic_sections, synthesis_prompts, chart_svgs)
        and typed models (profile, portfolio, communications) for NBA generation.
    """
    if mcp_client:
        logger.info("fetch_report_data started: client_id=%s", client_id)
        names = _build_tool_name_map(mcp_client, ["get_client_report_data"])
        result = mcp_client.call_tool_sync(
            "get_client_report_data_001", names["get_client_report_data"], {"client_id": client_id}
        )
        data = _extract_mcp_data(result)
    else:
        logger.info("fetch_report_data started: client_id=%s", client_id)
        _client = _get_mcp_client()
        with _client as client:
            names = _build_tool_name_map(client, ["get_client_report_data"])
            result = client.call_tool_sync(
                "get_client_report_data_001", names["get_client_report_data"], {"client_id": client_id}
            )
            data = _extract_mcp_data(result)

    if "error" in data:
        raise RuntimeError(f"MCP get_client_report_data failed: {data['error']}")

    logger.info("fetch_report_data completed: client_id=%s keys=%s", client_id, list(data.keys()))

    # Build report-shaped models via transformers
    profile = build_client_profile(data["client"], data["restrictions"], data["accounts"], data["transactions"])
    portfolio_model = build_portfolio(
        data["holdings_with_securities"],
        data["performance"],
        data["transactions"],
        data.get("income_expense"),
        data["portfolios"][0] if data["portfolios"] else None,
    )
    communications = build_communications(data["interactions"])
    market_context = build_market_context(data["themes"], date.today())

    generator = ReportGenerator()
    components = generator.generate(
        profile, portfolio_model, communications, data["recommended_products"], market_context
    )

    return ReportData(
        components=components,
        profile=profile,
        portfolio=portfolio_model,
        communications=communications,
    )


def save_report_via_mcp(
    report_id: str,
    client_id: str,
    s3_path: str,
    generated_date: str,
    status: str,
    next_best_action: str | None = None,
    mcp_client=None,
) -> None:
    """Save a report record to Redshift via the Portfolio Data Server MCP."""
    payload = {
        "report_id": report_id,
        "client_id": client_id,
        "s3_path": s3_path,
        "generated_date": generated_date,
        "status": status,
        "next_best_action": next_best_action,
    }
    if mcp_client:
        logger.info("save_report_via_mcp started: report_id=%s", report_id)
        names = _build_tool_name_map(mcp_client, ["save_report"])
        result = mcp_client.call_tool_sync("save_report_001", names["save_report"], payload)
        data = _extract_mcp_data(result)
        if "error" in data:
            raise RuntimeError(f"MCP save_report failed: {data['error']}")
        logger.info("save_report_via_mcp completed: report_id=%s", report_id)
    else:
        logger.info("save_report_via_mcp started: report_id=%s", report_id)
        _client = _get_mcp_client()
        with _client as client:
            names = _build_tool_name_map(client, ["save_report"])
            result = client.call_tool_sync("save_report_001", names["save_report"], payload)
            data = _extract_mcp_data(result)
            if "error" in data:
                raise RuntimeError(f"MCP save_report failed: {data['error']}")
            logger.info("save_report_via_mcp completed: report_id=%s", report_id)
