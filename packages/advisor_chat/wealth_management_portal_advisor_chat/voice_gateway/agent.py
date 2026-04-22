"""Voice Gateway Agent — tools and config for BidiAgent that delegates to specialist A2A agents."""

import json
import logging
import os
from uuid import uuid4

import boto3
import botocore.config
import httpx
from strands import tool

logger = logging.getLogger(__name__)

# Specialist agent endpoints (matches routing agent)
DATABASE_AGENT_ARN = os.environ.get("DATABASE_AGENT_ARN")
STOCK_DATA_AGENT_ARN = os.environ.get("STOCK_DATA_AGENT_ARN")
WEB_SEARCH_ARN = os.environ.get("WEB_SEARCH_AGENT_ARN")

DATABASE_AGENT_URL = os.environ.get("DATABASE_AGENT_URL", "http://localhost:9001")
STOCK_DATA_AGENT_URL = os.environ.get("STOCK_DATA_AGENT_URL", "http://localhost:9002")
WEB_SEARCH_URL = os.environ.get("WEB_SEARCH_AGENT_URL", "http://localhost:9004")

_agentcore_client = None


def _get_agentcore_client():
    global _agentcore_client
    if _agentcore_client is None:
        _agentcore_client = boto3.client(
            "bedrock-agentcore",
            region_name=os.environ.get("AWS_REGION", "us-west-2"),
            config=botocore.config.Config(read_timeout=120),
        )
    return _agentcore_client


def _call_a2a_http(endpoint: str, question: str) -> str:
    """Send a message to an A2A agent via HTTP (local dev)."""
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "role": "user",
                "messageId": uuid4().hex,
                "parts": [{"kind": "text", "text": question}],
            }
        },
    }
    resp = httpx.post(f"{endpoint}/", json=msg, timeout=120)
    resp.raise_for_status()
    result = resp.json().get("result", {})

    for artifact in result.get("artifacts", []):
        for part in artifact.get("parts", []):
            if part.get("kind") == "text" and part.get("text"):
                return part["text"]

    for m in reversed(result.get("history", [])):
        if m.get("role") == "agent":
            for part in m.get("parts", []):
                if part.get("kind") == "text" and not part["text"].startswith("<thinking"):
                    return part["text"]

    return "No response from agent."


def _call_agent(arn: str | None, url: str, question: str) -> str:
    """Call agent via AgentCore (if ARN set) or HTTP (local dev)."""
    if arn:
        logger.info("Calling agent via AgentCore: %s", arn)
        client = _get_agentcore_client()
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "message/send",
                "params": {
                    "message": {
                        "kind": "message",
                        "role": "user",
                        "messageId": uuid4().hex,
                        "parts": [{"kind": "text", "text": question}],
                    }
                },
            }
        )
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeSessionId=f"voice-{uuid4().hex}",
            payload=payload.encode(),
        )
        body = json.loads(resp["response"].read())
        result = body.get("result", {})
        for artifact in result.get("artifacts", []):
            for part in artifact.get("parts", []):
                if part.get("kind") == "text" and part.get("text"):
                    return part["text"]
        return str(body)
    else:
        logger.info("Calling agent via HTTP: %s", url)
        return _call_a2a_http(url, question)


@tool
def ask_database_agent(question: str) -> str:
    """Ask about clients, portfolios, holdings, AUM, reports, or advisor metrics.

    Use for: client search, profiles, portfolio holdings, investment details,
    AUM trends, net worth, risk tolerance, goals, client reports, fee analysis.

    Args:
        question: Natural language question about a client, portfolio, or advisor data.
    """
    return _call_agent(DATABASE_AGENT_ARN, DATABASE_AGENT_URL, question)


@tool
def ask_stock_data_agent(question: str) -> str:
    """Ask about stock prices, market data, or sector performance.

    Use for: live stock quotes, price history, sector analysis, market performance.

    Args:
        question: Natural language question about stocks or market data.
    """
    return _call_agent(STOCK_DATA_AGENT_ARN, STOCK_DATA_AGENT_URL, question)


@tool
def ask_web_search_agent(question: str) -> str:
    """Ask about news, articles, and market themes.

    Use for: recent news, financial headlines, market trends, current events.

    Args:
        question: Natural language question about news or market themes.
    """
    return _call_agent(WEB_SEARCH_ARN, WEB_SEARCH_URL, question)


SYSTEM_PROMPT = (
    "You are a voice-enabled Wealth Management Assistant for financial advisors. "
    "You route questions to specialist agents:\n"
    "1. ask_database_agent — Client info: portfolios, holdings, AUM, reports, advisor metrics, fees\n"
    "2. ask_stock_data_agent — Markets: stock prices, sector analysis, market performance\n"
    "3. ask_web_search_agent — News, market themes, current events\n\n"
    "Rules:\n"
    "- Route to the RIGHT specialist. If the intent is clear, call the specialist immediately.\n"
    "- For questions spanning multiple domains, call multiple agents.\n"
    "- Return the specialist's response verbatim. Do NOT reformat or summarize.\n"
    "- Never fabricate data — only use what the agents return.\n"
    "- Keep responses concise and natural for voice conversation.\n"
    "- Do NOT end with follow-up questions."
)

TOOLS = [
    ask_database_agent,
    ask_stock_data_agent,
    ask_web_search_agent,
]
