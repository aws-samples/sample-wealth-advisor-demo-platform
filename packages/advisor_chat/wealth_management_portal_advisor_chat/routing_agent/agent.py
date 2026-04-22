"""Routing Agent — supervisor that delegates to specialist A2A agents.

Uses A2A Agent for AgentCore endpoints (production) or httpx for localhost (local dev).
"""

import contextvars
import json
import logging
import os
from uuid import uuid4

import boto3
import botocore.config
import httpx
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, tool
from strands.models.bedrock import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

SCHEDULER_GATEWAY_URL = os.environ.get("SCHEDULER_GATEWAY_URL")
EMAIL_SENDER_GATEWAY_URL = os.environ.get("EMAIL_SENDER_GATEWAY_URL")

# AgentCore ARNs (production) or localhost URLs (local dev)
DATABASE_ARN = os.environ.get("DATABASE_AGENT_ARN")
STOCK_DATA_ARN = os.environ.get("STOCK_DATA_AGENT_ARN")
WEB_SEARCH_ARN = os.environ.get("WEB_SEARCH_AGENT_ARN")

DATABASE_URL = os.environ.get("DATABASE_AGENT_URL", "http://localhost:9001")
STOCK_DATA_URL = os.environ.get("STOCK_DATA_AGENT_URL", "http://localhost:9002")
WEB_SEARCH_URL = os.environ.get("WEB_SEARCH_AGENT_URL", "http://localhost:9004")

_agentcore_client = None

# Capture last tool result so /invocations can use it when str(AgentResult) is empty
_last_tool_result = ""

# Sources extracted from web search tool result (before LLM can strip the tag)
_last_sources: list | None = None

# Raw AgentCore result dict — lets tool wrappers inspect extra artifacts
_last_agentcore_result: dict = {}

# Server-side identity — set before calling the agent, read by scheduler tools
current_user_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_user_id", default="")

# Streaming queue — set by main.py when SSE streaming is active, read by tool functions
_stream_queue: contextvars.ContextVar[object | None] = contextvars.ContextVar("_stream_queue", default=None)


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

    # Extract text from artifacts
    for artifact in result.get("artifacts", []):
        for part in artifact.get("parts", []):
            if part.get("kind") == "text" and part.get("text"):
                return part["text"]

    # Fallback: check history for last agent message
    for msg in reversed(result.get("history", [])):
        if msg.get("role") == "agent":
            for part in msg.get("parts", []):
                if part.get("kind") == "text" and not part["text"].startswith("<thinking"):
                    return part["text"]

    return "No response from agent."


def _call_a2a_http_stream(endpoint: str, question: str, queue: object) -> str:
    """Stream from a sub-agent's /stream endpoint, pushing tokens to the queue."""
    import urllib.parse

    url = f"{endpoint}/stream?message={urllib.parse.quote(question)}"
    full_text = ""
    with httpx.stream("GET", url, timeout=120) as resp:
        resp.raise_for_status()
        buffer = ""
        event_type = ""
        for chunk in resp.iter_text():
            buffer += chunk
            lines = buffer.split("\n")
            buffer = lines.pop()
            for line in lines:
                if line.startswith("event: "):
                    event_type = line[7:].strip()
                elif line.startswith("data: ") and event_type:
                    try:
                        data = json.loads(line[6:])
                        if event_type == "token":
                            queue.put_nowait(("sub_token", data.get("text", "")))
                        elif event_type == "status":
                            queue.put_nowait(("sub_status", data.get("message", "")))
                        elif event_type == "done":
                            full_text = data.get("message", full_text)
                    except (ValueError, TypeError):
                        pass
                    event_type = ""
    return full_text or "No response from agent."


def _call_agent(arn: str | None, url: str, question: str) -> str:
    """Call agent via AgentCore invoke_agent_runtime (if ARN set) or HTTP (local dev).

    When a streaming queue is active, uses the /stream endpoint for local dev
    to push tokens in real time.
    """
    queue = _stream_queue.get(None)

    # Local dev with streaming — use SSE stream
    if not arn and queue:
        return _call_a2a_http_stream(url, question, queue)

    # Production or non-streaming — use blocking call
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
            runtimeSessionId=f"routing-{uuid4().hex}",
            payload=payload.encode(),
        )
        body = json.loads(resp["response"].read())
        logger.info("Agent response body keys: %s", list(body.keys()))
        result = body.get("result", {})
        _last_agentcore_result.clear()
        _last_agentcore_result.update(result if isinstance(result, dict) else {})
        logger.info(
            "Agent result keys: %s, artifacts: %s",
            list(result.keys()) if isinstance(result, dict) else type(result),
            len(result.get("artifacts", [])) if isinstance(result, dict) else "N/A",
        )
        texts = []
        for artifact in result.get("artifacts", []):
            for part in artifact.get("parts", []):
                if part.get("kind") == "text" and part.get("text"):
                    texts.append(part["text"])
        if texts:
            logger.info("Got %d text parts from artifacts", len(texts))
            return "\n".join(texts)
        logger.warning("No text in artifacts, full body: %.500s", str(body))
        return str(body)
    else:
        logger.info("Calling agent via HTTP: %s", url)
        return _call_a2a_http(url, question)


def _make_gateway_mcp_client(gateway_url: str) -> MCPClient:
    """Create an MCP client for an AgentCore Gateway URL using SigV4 auth."""
    from common_auth import SigV4HTTPXAuth

    region = os.environ.get("AWS_REGION", "us-west-2")
    creds = boto3.Session(region_name=region).get_credentials().get_frozen_credentials()
    auth = SigV4HTTPXAuth(creds, region)
    return MCPClient(lambda: streamablehttp_client(gateway_url, auth=auth, timeout=120, terminate_on_close=False))


def _call_gateway_tool(gateway_url: str, tool_name: str, tool_args: dict) -> str:
    """Call a tool on an AgentCore Gateway MCP endpoint."""
    mcp_client = _make_gateway_mcp_client(gateway_url)
    with mcp_client as client:
        tools = client.list_tools_sync()
        resolved = tool_name
        for t in tools:
            if t.tool_name == tool_name or t.tool_name.endswith(f"___{tool_name}"):
                resolved = t.tool_name
                break
        result = client.call_tool_sync(f"{tool_name}_001", resolved, tool_args)
    content = result.get("content", [])
    return content[0]["text"] if content else ""


@tool
def ask_database_agent(question: str) -> str:
    """Ask the Database Agent about client data, portfolios, holdings, AUM, and reports.

    Use for: client profiles, portfolio queries, holdings, AUM trends, client reports

    Args:
        question: Natural language question about client data or reports

    Returns:
        Agent's response with the requested client or portfolio information
    """
    global _last_tool_result
    _last_tool_result = _call_agent(DATABASE_ARN, DATABASE_URL, question)
    return _last_tool_result


@tool
def ask_stock_data_agent(question: str) -> str:
    """
    Specialized stock data agent for comprehensive equity market analysis and financial metrics.

    Provides real-time and historical stock data, financial metrics, pricing information,
    and market analysis to support investment decision-making and portfolio management.

    Args:
        query (str): Stock ticker symbol or analysis request. Examples:
            - "AAPL" (for Apple Inc. current data)
            - "TSLA historical pricing last 6 months"
            - "MSFT financial metrics and ratios"
            - "SPY price and volume data"
        search_type (str): Type of stock analysis to perform. Options:
            - "general": Comprehensive stock analysis (default)
            - "pricing": Focus on current and historical pricing data
            - "metrics": Focus on financial metrics and ratios
            - "chart": Generate stock charts and comparison charts

    Returns:
        str: Comprehensive stock information containing:
            - Current stock pricing and market data
            - Historical pricing trends and patterns
            - Financial metrics and key ratios
            - Volume analysis and trading information
            - Market performance comparisons
            - Charts and visualizations when requested
            - Display the data in table format if it is comparison data

    Raises:
        Returns error message string if stock service unavailable or query fails
    """
    global _last_tool_result
    _last_tool_result = _call_agent(STOCK_DATA_ARN, STOCK_DATA_URL, question)
    return _last_tool_result


@tool
def ask_web_search_agent(question: str) -> str:
    """
    Advanced web search agent utilizing Tavily to retrieve comprehensive, accurate information from the internet.

    This agent provides intelligent web research capabilities for financial advisors, delivering structured,
    compliant results that adhere to professional standards and regulatory requirements.

    Args:
        query (str): The search query or question to research. Should be specific and well-formed.
        search_type (str): Type of search to perform. Options:
            - "general": Comprehensive search across multiple sources (default)
            - "news": Focus on recent news and current events
            - "answer": Direct answer-focused search for specific questions

    Returns:
        str: Structured response containing:
            - Comprehensive search findings with key insights
            - Source citations with publication dates and hyperlinks
            - Regulatory compliance considerations when applicable
            - Risk factors and limitations identified
    Raises:
        Returns error message string if client unavailable or search fails
    """
    global _last_tool_result, _last_sources
    _last_tool_result = _call_agent(WEB_SEARCH_ARN, WEB_SEARCH_URL, question)
    # Extract sources from the response (emitted as separate artifact by web search agent)
    import contextlib
    import json as _json
    import re as _re

    _last_sources = None
    m = _re.search(r"<!--SOURCES:(\[[\s\S]*?\])-->", _last_tool_result)
    if m:
        with contextlib.suppress(ValueError, TypeError):
            _last_sources = _json.loads(m.group(1))
    return _last_tool_result


@tool
def create_schedule(
    cron_expression: str,
    task_message: str,
    name: str,
    email: str,
    timezone: str = "UTC",
) -> str:
    """Create a recurring scheduled task.

    Args:
        cron_expression: EventBridge cron or rate expression, e.g. cron(0 16 * * ? *) or rate(6 hours).
        task_message: The message to replay through the routing agent on each scheduled run.
        name: Human-readable schedule name.
        email: Email address for result delivery.
        timezone: IANA timezone (default UTC).

    Returns:
        Confirmation message with schedule details.
    """
    user_id = current_user_id.get()
    if not user_id:
        return "No user identity available. Cannot create schedule."
    if not SCHEDULER_GATEWAY_URL:
        return "Scheduler gateway not configured."
    return _call_gateway_tool(
        SCHEDULER_GATEWAY_URL,
        "create_schedule",
        {
            "cron_expression": cron_expression,
            "task_message": task_message,
            "name": name,
            "user_id": user_id,
            "email": email,
            "timezone": timezone,
        },
    )


@tool
def list_schedules() -> str:
    """List all recurring schedules for a user.

    Returns:
        List of schedules with their details.
    """
    user_id = current_user_id.get()
    if not user_id:
        return "No user identity available. Cannot list schedules."
    if not SCHEDULER_GATEWAY_URL:
        return "Scheduler gateway not configured."
    return _call_gateway_tool(SCHEDULER_GATEWAY_URL, "list_schedules", {"user_id": user_id})


@tool
def delete_schedule(schedule_id: str) -> str:
    """Delete a recurring schedule.

    Args:
        schedule_id: Schedule ID to delete.

    Returns:
        Confirmation of deletion.
    """
    user_id = current_user_id.get()
    if not user_id:
        return "No user identity available. Cannot delete schedule."
    if not SCHEDULER_GATEWAY_URL:
        return "Scheduler gateway not configured."
    return _call_gateway_tool(
        SCHEDULER_GATEWAY_URL, "delete_schedule", {"schedule_id": schedule_id, "user_id": user_id}
    )


@tool
def toggle_schedule(schedule_id: str, enabled: bool) -> str:
    """Enable or disable a recurring schedule.

    Args:
        schedule_id: Schedule ID.
        enabled: True to enable, False to disable.

    Returns:
        Confirmation of the state change.
    """
    user_id = current_user_id.get()
    if not user_id:
        return "No user identity available. Cannot toggle schedule."
    if not SCHEDULER_GATEWAY_URL:
        return "Scheduler gateway not configured."
    return _call_gateway_tool(
        SCHEDULER_GATEWAY_URL, "toggle_schedule", {"schedule_id": schedule_id, "user_id": user_id, "enabled": enabled}
    )


@tool
def send_email(to: str, subject: str, body: str, attachment_url: str = "") -> str:
    """Send an email via SES. Use this to deliver scheduled task results.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body text.
        attachment_url: Optional S3 URL for file attachment.

    Returns:
        Confirmation of email delivery.
    """
    if not EMAIL_SENDER_GATEWAY_URL:
        return "Email sender gateway not configured."
    args: dict = {"to": to, "subject": subject, "body": body}
    if attachment_url:
        args["attachment_url"] = attachment_url
    return _call_gateway_tool(EMAIL_SENDER_GATEWAY_URL, "send_email", args)


SYSTEM_PROMPT = """You are the Wealth Management Chat Assistant for financial advisors.

Your role is to:
1. Understand user intent
2. Route the request to the correct specialized agent(s)
3. Combine responses only when necessary

You DO NOT answer questions yourself.
You ONLY delegate to tools.

---
## AVAILABLE AGENTS

1. ask_stock_data_agent
→ Stock prices, comparisons, financial metrics (Yahoo Finance only)

2. ask_database_agent
→ Client data, portfolios, AUM, advisor insights

3. ask_web_search_agent
→ Market news, events, macro trends, external insights

---
## INTENT CLASSIFICATION (CRITICAL)

Classify each query into ONE of the following:

---
### 1. STOCK_DATA
→ ask_stock_data_agent

Examples:
- "What’s AAPL price?"
- "Compare Amazon and Google"
- "How is Tesla doing?"

---

### 2. CLIENT_DATA
→ ask_database_agent

Examples:
- "Show Jennifer Bell’s portfolio"
- "Which clients have >1M AUM?"
- "How is my book of business performing?"
- "Show me fee revenue this quarter"
- "What's my AUM trend?"
- "Who are my UHNW clients?"
- "Show me Brittney's report" or "Get report for CL00001"

---

### 3. MARKET_NEWS
→ ask_web_search_agent

Examples:
- "What happened in market today?"
- "Why is tech down?"
- "Show retirement strategies in Boston?"

---
### 4. COMPOSITE (MULTI-DOMAIN)

If query combines:
- client/portfolio data
AND
- market/news context

→ Multi-step orchestration

---
## SYSTEM TOOLS

4. **Scheduling tools** — Create and manage recurring tasks:
   - Use **create_schedule** when a user asks to schedule a recurring task.
     Parse natural language time expressions into EventBridge cron expressions:
       "at 4pm every day"          → cron(0 16 * * ? *)
       "every Monday at 9am"       → cron(0 9 ? * MON *)
       "every hour"                → rate(1 hour)
       "every 6 hours"             → rate(6 hours)
     Required params: cron_expression, task_message (what to run), name (human-readable), email.
     If the user does not provide an email address, you MUST ask for it before calling create_schedule.
     Do NOT invent an email.
     If the user specifies a timezone (e.g. "4pm Eastern", "9am PST"), pass the IANA timezone
     (e.g. "America/New_York", "America/Los_Angeles") in the timezone parameter and use the
     user's stated time directly in the cron expression — do NOT convert to UTC (EventBridge handles
     the conversion using the timezone parameter).
     E.g. "5pm Eastern" → cron(0 17 * * ? *) + timezone="America/New_York".
     If no timezone is mentioned, ask the user for their timezone before creating the schedule.
   - Use **list_schedules** when a user asks to see their schedules.
   - Use **delete_schedule** when a user asks to delete or cancel a schedule.
   - Use **toggle_schedule** when a user asks to pause or resume a schedule.

## Message context

5. **send_email** — Deliver results via email:
   - Use when executing a scheduled task (message starts with "[Scheduled Task: ...]").
   - Extract the recipient email from the line "Deliver results via email to: <email>".
   - Call the appropriate specialist agent(s) to get the results, then call send_email
     with the results as the body.

## Scheduled Task Execution
When you receive a message starting with "[Scheduled Task: ...]":
1. Extract the email from the "Deliver results via email to:" line.
2. Extract the task from the "Task:" line.
3. Call the appropriate specialist agent tool FIRST and wait for its response.
4. ONLY AFTER you have the specialist agent's actual response, call send_email
   with: to=<email>, subject=<schedule name>, body=<actual results from step 3>.
5. If the specialist agent fails or returns an error, call send_email with
   a clear error message as the body.

CRITICAL: NEVER call send_email before you have real results. Do NOT use
placeholder text like "Getting..." or "Fetching..." as the email body.

---

## ROUTING PRINCIPLES (CRITICAL)

- Be precise — call ONLY the required agent(s) or tools
- Prefer a single agent when intent is clear
- Use multiple agents ONLY when necessary
- Avoid unnecessary calls (latency + duplication)

---

## SMART CONTEXT ENRICHMENT

For stock-related queries:

If query implies:
- "how is"
- "performance"
- "what’s happening"

→ Call:
1. ask_stock_data_agent
2. ask_web_search_agent (for context)

---

## COMPOSITE EXECUTION

For portfolio + market queries:

1. Call ask_database_agent
2. Extract assets/tickers
3. Call ask_web_search_agent with those assets
4. Combine:

Client / Portfolio Data:
<client output>

Market Insights:
<web output>

---

## STRUCTURED MARKET OUTPUT (CRITICAL)

For any stock-related query, you MUST return structured market data.

Return a JSON object with:

{
  "tickers": ["AAPL", "MSFT"],
  "intent": "single" | "comparison" | "market",
  "requiresChart": true
}

Rules:
- Include ALL relevant tickers
- Use "comparison" if multiple stocks
- Use "single" if one stock
- Use "market" for broad queries (SPY, QQQ, etc.)
- Do NOT include explanation inside JSON
- JSON should be separate from natural language response
---
### Ticker Resolution

- First: use known mappings (Apple→AAPL, etc.)
- If not found:
  → infer from context
  → or pass company name directly to tool
---

Rules:
- Specific stock query → chart those tickers: <!--CHART:["AAPL"]-->
- Stock comparison → chart all compared tickers: <!--CHART:["AAPL","MSFT"]-->
- Broad market query ("what happened to the market", "market overview",
  "how are markets doing") → call BOTH ask_stock_data_agent (for SPY, QQQ, DIA
  quotes) AND ask_web_search_agent (for news), then: <!--CHART:["SPY","QQQ","DIA"]-->
- Non-market queries (retirement, taxes, compliance, client profiles) → NO chart tag
- Only add the tag when a visual stock chart adds value to the answer
- Prefer action over clarification. If the intent is reasonably clear,
  call the tool immediately.
- Never fabricate data — only use what the tools return.
- CRITICAL: When a tool returns markdown links (e.g. [Download Report](url)),
  you MUST include them EXACTLY as-is in your response. Never omit, summarize,
  or paraphrase download URLs or presigned links.
- Do NOT end with follow-up questions. Just answer."""

TOOLS = [
    ask_stock_data_agent,
    ask_database_agent,
    ask_web_search_agent,
    create_schedule,
    list_schedules,
    delete_schedule,
    toggle_schedule,
    send_email,
]

MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID", "")


def create_agent(session_id: str = "", user_id: str = "", hooks: list | None = None, callback_handler=None) -> Agent:
    kwargs: dict = {
        "name": "Wealth Management Chat Router",
        "description": "Routes advisor questions to specialist agents for clients, markets, and compliance.",
        "model": BedrockModel(
            model_id=os.environ.get("ROUTING_BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
        ),
        "system_prompt": SYSTEM_PROMPT,
        "tools": TOOLS,
        "callback_handler": callback_handler,
    }
    if hooks:
        kwargs["hooks"] = hooks

    if session_id:
        try:
            from ..common.memory import get_ltm_id, get_stm_id

            stm_id = get_stm_id()
            ltm_id = get_ltm_id()
            memory_id = ltm_id or stm_id
            if memory_id:
                from bedrock_agentcore.memory.integrations.strands.config import (
                    AgentCoreMemoryConfig,
                    RetrievalConfig,
                )
                from bedrock_agentcore.memory.integrations.strands.session_manager import (
                    AgentCoreMemorySessionManager,
                )

                region = os.environ.get("AWS_REGION", "us-west-2")
                retrieval = {}
                if ltm_id and memory_id == ltm_id:
                    retrieval = {
                        "/knowledge/{actorId}/": RetrievalConfig(top_k=10, relevance_score=0.3),
                        "/summaries/{actorId}/{sessionId}/": RetrievalConfig(top_k=3, relevance_score=0.5),
                    }
                config = AgentCoreMemoryConfig(
                    memory_id=memory_id,
                    session_id=session_id,
                    actor_id=user_id or session_id,
                    retrieval_config=retrieval,
                )
                kwargs["session_manager"] = AgentCoreMemorySessionManager(
                    agentcore_memory_config=config,
                    region_name=region,
                )
                logger.info("AgentCore Memory enabled: memory=%s session=%s", memory_id, session_id)
        except Exception:
            logger.exception("Failed to initialize AgentCore Memory, continuing without it")

    return Agent(**kwargs)
