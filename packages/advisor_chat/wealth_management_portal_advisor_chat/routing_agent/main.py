"""Routing Agent — FastAPI server with SSE streaming + A2A server.

Exposes:
- POST /chat          — sync JSON response (backward compatible with existing UI)
- GET  /chat/stream   — SSE streaming with status updates
- A2A  /              — standard A2A protocol endpoint (for other agents to call)
"""

import asyncio
import contextvars
import logging
import os
import re
from pathlib import Path

import jwt
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[4] / ".env")
except IndexError:
    load_dotenv()  # In container, use default .env search or env vars

from strands.multiagent.a2a import A2AServer  # noqa: E402

from ..common.market_data import build_market_data  # noqa: E402
from ..common.streaming import (  # noqa: E402
    agent_end_event,
    agent_start_event,
    done_event,
    error_event,
    status_event,
    token_event,
)


def _extract_sources(text: str) -> list | None:
    """Parse <!--SOURCES:[...]-->  from agent response."""
    import json as _json

    m = re.search(r"<!--SOURCES:(\[[\s\S]*?\])-->", text)
    if not m:
        return None
    try:
        return _json.loads(m.group(1))
    except (ValueError, TypeError):
        return None


def _extract_chart_market_data(text: str):
    """Parse <!--CHART:["SPY","QQQ"]--> from agent response and build chart data."""
    import json as _json

    m = re.search(r"<!--CHART:(\[.*?\])-->", text)
    if not m:
        return None
    try:
        tickers = _json.loads(m.group(1))
    except (ValueError, TypeError):
        return None
    if not tickers:
        return None
    data = build_market_data({"tickers": tickers})
    return data if data and data.get("quotes") else None


from . import agent as _agent_mod  # noqa: E402
from .agent import create_agent  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))

_USER_ID_RE = re.compile(r"^\[user_id=([^\]]+)\]\s*")

EXECUTOR_CLIENT_ID = os.environ.get("EXECUTOR_CLIENT_ID", "")
LOCAL_DEV = os.environ.get("LOCAL_DEV", "").lower() == "true"


def _extract_user_id(text: str) -> tuple[str, str]:
    """Extract [user_id=X] prefix from message. Returns (user_id, cleaned_text)."""
    m = _USER_ID_RE.match(text)
    if m:
        return m.group(1), text[m.end() :]
    return "", text


def _resolve_user_id(request: Request) -> str:
    """Extract user identity from a verified Cognito JWT.

    Validates the JWT signature via JWKS, then extracts user identity.
    Falls back to unverified decode only in LOCAL_DEV mode.
    """
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return ""
    token = auth.removeprefix("Bearer ")
    try:
        if LOCAL_DEV:
            # Local dev: no Cognito available, decode without verification
            claims = jwt.decode(token, options={"verify_signature": False})
        else:
            from .jwt_validator import decode_and_verify

            claims = decode_and_verify(token)
    except Exception:
        logger.warning("JWT validation failed", exc_info=True)
        return ""
    # Executor path — trusted service caller, user_id from dedicated header
    if claims.get("client_id") == EXECUTOR_CLIENT_ID and EXECUTOR_CLIENT_ID:
        return request.headers.get("x-amzn-bedrock-agentcore-runtime-custom-userid", "")
    # Browser path — sub is the Cognito user identity
    return claims.get("sub", "")


# --- FastAPI app for UI-facing endpoints ---

_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "").split(",") if os.environ.get("ALLOWED_ORIGINS") else ["*"]
app = FastAPI(title="WealthManagement Chat Router")
app.add_middleware(CORSMiddleware, allow_origins=_allowed_origins, allow_methods=["*"], allow_headers=["*"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    client_id: str | None = None


class ChatResponse(BaseModel):
    message: str
    stockData: dict | None = None
    marketData: dict | None = None


def _strip_thinking(text: str) -> str:
    import re

    return re.sub(r"<thinking>[\s\S]*?</thinking>\s*", "", text).strip()


def _strip_internal_tags(text: str) -> str:
    """Remove internal tags (QUOTES, MARKET_DATA, CHART) before sending to user."""
    import re

    return re.sub(r"<!--(?:QUOTES|MARKET_DATA|CHART|SOURCES):[\s\S]*?-->", "", text).strip()


@app.post("/chat")
async def chat_sync(body: ChatRequest, request: Request) -> ChatResponse:
    """Synchronous chat — backward compatible with existing ImprovedChatWidget."""
    try:
        prompt = body.message
        if LOCAL_DEV:
            user_id, prompt = _extract_user_id(prompt)
        else:
            user_id = _resolve_user_id(request)
        if body.client_id:
            prompt = f"[client_id={body.client_id}] {prompt}"

        agent = create_agent(session_id=body.session_id, user_id=user_id)
        _agent_mod.current_user_id.set(user_id)
        _agent_mod._last_tool_result = ""
        result = await asyncio.to_thread(agent, prompt)
        text = str(result) if result else ""
        text = _strip_thinking(text)
        if not text:
            text = _agent_mod._last_tool_result.strip()
        if not text:
            text = "I couldn't process that request."
        market = await asyncio.to_thread(_extract_chart_market_data, text)
        return ChatResponse(message=_strip_internal_tags(text), marketData=market)
    except Exception as e:
        logger.exception("Chat error")
        return ChatResponse(message=f"Sorry, I encountered an error: {e}")


_TOOL_LABELS = {
    "ask_database_agent": "Consulting Database Agent",
    "ask_stock_data_agent": "Consulting Stock Data Agent",
    "ask_web_search_agent": "Consulting Web Search Agent",
    "create_schedule": "Creating schedule",
    "list_schedules": "Listing schedules",
    "delete_schedule": "Deleting schedule",
    "toggle_schedule": "Toggling schedule",
    "send_email": "Sending email",
}


@app.get("/chat/stream")
async def chat_stream(
    request: Request,
    message: str = Query(...),
    session_id: str = Query(""),
    client_id: str | None = Query(None),
):
    """SSE streaming chat — streams text tokens and tool status in real time."""

    async def event_generator():
        try:
            prompt = message
            if LOCAL_DEV:
                user_id, prompt = _extract_user_id(prompt)
            else:
                user_id = _resolve_user_id(request)
            if client_id:
                prompt = f"[client_id={client_id}] {prompt}"

            yield status_event("Analyzing your question...")

            # Queue for tool status events only (no tokens during tool calls)
            queue: asyncio.Queue = asyncio.Queue()

            from strands.hooks import HookProvider, HookRegistry
            from strands.hooks.events import AfterToolCallEvent, BeforeToolCallEvent

            _AGENT_TOOLS = {"ask_stock_data_agent", "ask_database_agent", "ask_web_search_agent"}

            class ToolStatusHooks(HookProvider):
                def register_hooks(self, registry: HookRegistry) -> None:
                    registry.add_callback(BeforeToolCallEvent, self._before)
                    registry.add_callback(AfterToolCallEvent, self._after)

                def _before(self, event: BeforeToolCallEvent) -> None:
                    name = event.tool_use.get("name", "")
                    label = _TOOL_LABELS.get(name, name.replace("_", " ").title())
                    if name in _AGENT_TOOLS:
                        queue.put_nowait(("agent_start", label))
                    queue.put_nowait(("status", f"{label}..."))

                def _after(self, event: AfterToolCallEvent) -> None:
                    name = event.tool_use.get("name", "")
                    label = _TOOL_LABELS.get(name, name.replace("_", " ").title())
                    queue.put_nowait(("status", f"{label} ✓"))
                    if name in _AGENT_TOOLS:
                        queue.put_nowait(("agent_end", label))

            # No callback_handler — don't stream intermediate tokens
            agent = create_agent(session_id=session_id, user_id=user_id, hooks=[ToolStatusHooks()])
            _agent_mod.current_user_id.set(user_id)
            _agent_mod._last_tool_result = ""
            _agent_mod._stream_queue.set(None)

            # Run agent in background thread, copying contextvars so tools see current_user_id
            loop = asyncio.get_event_loop()
            ctx = contextvars.copy_context()
            agent_task = loop.run_in_executor(None, ctx.run, agent, prompt)

            while True:
                while not queue.empty():
                    kind, payload = queue.get_nowait()
                    if kind == "agent_start":
                        yield agent_start_event(payload)
                    elif kind == "agent_end":
                        yield agent_end_event(payload)
                    else:
                        yield status_event(payload)

                if agent_task.done():
                    break
                await asyncio.sleep(0.05)

            # Drain remaining status events
            while not queue.empty():
                kind, payload = queue.get_nowait()
                if kind == "agent_start":
                    yield agent_start_event(payload)
                elif kind == "agent_end":
                    yield agent_end_event(payload)
                else:
                    yield status_event(payload)

            result = agent_task.result()
            text = str(result) if result else ""
            text = _strip_thinking(text)
            if not text:
                text = _agent_mod._last_tool_result.strip()
            if not text:
                text = "I couldn't process that request."

            market = await asyncio.to_thread(_extract_chart_market_data, text)
            sources = _extract_sources(text)
            clean = _strip_internal_tags(text)

            # Stream the final response text token-by-token for typewriter effect
            yield status_event("Generating response...")
            chunk_size = 12
            for i in range(0, len(clean), chunk_size):
                yield token_event(clean[i : i + chunk_size])
                await asyncio.sleep(0.01)

            yield done_event(clean, market_data=market, sources=sources)

        except Exception as e:
            logger.exception("Stream error")
            yield error_event(str(e))

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/chart")
async def get_chart(
    tickers: str = Query(..., description="Comma-separated tickers"),
    range: str = Query("1M"),
):
    """Lightweight chart data endpoint — no agent call, just yfinance."""
    data = await asyncio.to_thread(build_market_data, {"tickers": tickers.split(","), "timeRange": range})
    return data


@app.get("/chat/sessions")
async def list_sessions(request: Request):
    """List conversation sessions from AgentCore memory."""
    try:
        from ..common.memory import list_session_events

        events = list_session_events(max_results=50)
        if not events:
            return {"sessions": []}

        # Group by session_id, extract first user message as title
        sessions: dict[str, dict] = {}
        for ev in events:
            sid = ev.get("session_id") or ev.get("sessionId", "")
            if not sid or sid in sessions:
                continue
            title = ""
            messages = ev.get("messages", ev.get("content", []))
            if isinstance(messages, list):
                for msg in messages:
                    m = msg if isinstance(msg, dict) else vars(msg)
                    if m.get("role") == "user":
                        content = m.get("content", "")
                        if isinstance(content, list):
                            for block in content:
                                b = block if isinstance(block, dict) else vars(block)
                                if isinstance(b.get("text"), str):
                                    title = b["text"][:80]
                                    break
                        elif isinstance(content, str):
                            title = content[:80]
                        if title:
                            break
            sessions[sid] = {
                "session_id": sid,
                "title": title or f"Conversation {sid[:8]}",
                "created_at": ev.get("created_at") or ev.get("createdAt", ""),
            }

        return {"sessions": list(sessions.values())[:20]}
    except Exception:
        logger.debug("Failed to list sessions", exc_info=True)
        return {"sessions": []}


@app.post("/chat/sessions/{session_id}/close")
async def close_session_endpoint(session_id: str):
    """Signal that a chat session window was closed. Flushes memory if active."""
    try:
        from ..common.memory import close_session

        close_session(session_id)
    except Exception:
        logger.debug("Failed to close session", exc_info=True)
    return {"status": "closed", "session_id": session_id}


@app.get("/health")
def health():
    return {"status": "ok", "service": "wealth-management-chat-router"}


@app.get("/ping")
def ping():
    return ""


@app.post("/invocations")
async def invocations(request: Request):
    """AgentCore HTTP protocol endpoint — receives A2A JSON-RPC payload.

    Supports SSE streaming when Accept: text/event-stream is set.
    """
    import json as _json

    body = await request.body()
    logger.info("Invocation payload: %s", body[:500])
    payload = _json.loads(body)

    # Extract text from A2A message/send
    text = ""
    params = payload.get("params", {})
    msg = params.get("message", {})
    for part in msg.get("parts", []):
        if part.get("kind") == "text":
            text = part.get("text", "")
            break

    if not text:
        return {"jsonrpc": "2.0", "id": payload.get("id", 1), "error": {"code": -32600, "message": "No text found"}}

    # Fast path: chart data requests bypass the LLM entirely
    if text.startswith("__chart__"):
        import json as _cjson

        from ..common.market_data import build_market_data as _build_market_data

        parts = text.split()
        tickers = parts[1].split(",") if len(parts) > 1 else []
        time_range = parts[2] if len(parts) > 2 else "1M"
        data = await asyncio.to_thread(_build_market_data, {"tickers": tickers, "timeRange": time_range})
        return {
            "jsonrpc": "2.0",
            "id": payload.get("id", 1),
            "result": {
                "artifacts": [
                    {"parts": [{"kind": "text", "text": ""}]},
                    {"parts": [{"kind": "text", "text": f"<!--MARKET_DATA:{_cjson.dumps(data, default=str)}-->"}]},
                ],
            },
        }

    session_id = msg.get("messageId", "")
    accept = request.headers.get("accept", "")

    # SSE streaming path
    if "text/event-stream" in accept:

        async def _sse_invocation():
            try:
                nonlocal text
                if LOCAL_DEV:
                    user_id, text = _extract_user_id(text)
                else:
                    user_id = _resolve_user_id(request)

                yield status_event("Analyzing your question...")

                queue: asyncio.Queue = asyncio.Queue()

                from strands.hooks import HookProvider, HookRegistry
                from strands.hooks.events import AfterToolCallEvent, BeforeToolCallEvent

                _AGENT_TOOLS = {"ask_stock_data_agent", "ask_database_agent", "ask_web_search_agent"}

                class _Hooks(HookProvider):
                    def register_hooks(self, registry: HookRegistry) -> None:
                        registry.add_callback(BeforeToolCallEvent, self._before)
                        registry.add_callback(AfterToolCallEvent, self._after)

                    def _before(self, event: BeforeToolCallEvent) -> None:
                        name = event.tool_use.get("name", "")
                        label = _TOOL_LABELS.get(name, name.replace("_", " ").title())
                        if name in _AGENT_TOOLS:
                            queue.put_nowait(("agent_start", label))
                        queue.put_nowait(("status", f"{label}..."))

                    def _after(self, event: AfterToolCallEvent) -> None:
                        name = event.tool_use.get("name", "")
                        label = _TOOL_LABELS.get(name, name.replace("_", " ").title())
                        queue.put_nowait(("status", f"{label} ✓"))
                        if name in _AGENT_TOOLS:
                            queue.put_nowait(("agent_end", label))

                agent = create_agent(session_id=session_id, user_id=user_id, hooks=[_Hooks()])
                _agent_mod.current_user_id.set(user_id)
                _agent_mod._last_tool_result = ""
                _agent_mod._last_sources = None
                _agent_mod._stream_queue.set(None)

                # Copy contextvars so tools see current_user_id in the executor thread
                loop = asyncio.get_event_loop()
                ctx = contextvars.copy_context()
                agent_task = loop.run_in_executor(None, ctx.run, agent, text)

                while True:
                    while not queue.empty():
                        kind, p = queue.get_nowait()
                        if kind == "agent_start":
                            yield agent_start_event(p)
                        elif kind == "agent_end":
                            yield agent_end_event(p)
                        else:
                            yield status_event(p)
                    if agent_task.done():
                        break
                    await asyncio.sleep(0.05)

                while not queue.empty():
                    kind, p = queue.get_nowait()
                    if kind == "agent_start":
                        yield agent_start_event(p)
                    elif kind == "agent_end":
                        yield agent_end_event(p)
                    else:
                        yield status_event(p)

                result = agent_task.result()
                reply = str(result).strip() if result is not None else ""
                reply = _strip_thinking(reply)
                if not reply:
                    reply = _agent_mod._last_tool_result.strip()
                if not reply:
                    reply = "I couldn't process that request."

                market = await asyncio.to_thread(_extract_chart_market_data, reply)
                sources = _agent_mod._last_sources or _extract_sources(reply)
                clean = _strip_internal_tags(reply)

                yield status_event("Generating response...")
                chunk_size = 12
                for i in range(0, len(clean), chunk_size):
                    yield token_event(clean[i : i + chunk_size])
                    await asyncio.sleep(0.01)

                yield done_event(clean, market_data=market, sources=sources)

            except Exception as e:
                logger.exception("SSE invocation error")
                yield error_event(str(e))

        return StreamingResponse(_sse_invocation(), media_type="text/event-stream")

    # JSON path — existing behavior

    try:
        if LOCAL_DEV:
            user_id, text = _extract_user_id(text)
        else:
            user_id = _resolve_user_id(request)
        agent = create_agent(session_id=session_id, user_id=user_id)
        _agent_mod.current_user_id.set(user_id)
        _agent_mod._last_tool_result = ""
        _agent_mod._last_sources = None
        result = await asyncio.to_thread(agent, text)
        reply = str(result).strip() if result is not None else ""
        reply = _strip_thinking(reply)
        logger.info("Routing agent reply (len=%d): %.300s", len(reply), reply)
        if not reply:
            reply = _agent_mod._last_tool_result.strip()
            logger.info("Using _last_tool_result fallback (len=%d): %.300s", len(reply), reply)
        if not reply:
            reply = "I couldn't process that request. Could you try rephrasing?"
        market = await asyncio.to_thread(_extract_chart_market_data, reply)
    except Exception as e:
        logger.exception("Invocation error")
        reply = f"Sorry, I encountered an error: {e}"
        market = None

    sources = _agent_mod._last_sources

    return {
        "jsonrpc": "2.0",
        "id": payload.get("id", 1),
        "result": {
            "artifacts": [
                {"parts": [{"kind": "text", "text": _strip_internal_tags(reply)}]},
                *(
                    [{"parts": [{"kind": "text", "text": f"<!--MARKET_DATA:{_json.dumps(market, default=str)}-->"}]}]
                    if market
                    else []
                ),
                *([{"parts": [{"kind": "text", "text": f"<!--SOURCES:{_json.dumps(sources)}-->"}]}] if sources else []),
            ],
        },
    }


def serve():
    """Start the routing agent server.

    Runs the FastAPI app (with /chat and /chat/stream) on the configured port.
    The A2A protocol endpoint is also available for agent-to-agent communication.
    """
    # Create A2A server wrapping the routing agent
    agent = create_agent()
    a2a_server = A2AServer(agent=agent, host="0.0.0.0", port=PORT)

    # Get the underlying FastAPI app from A2A server and mount our custom routes
    a2a_app = a2a_server.to_fastapi_app()

    @a2a_app.middleware("http")
    async def log_requests(request, call_next):
        logger.info(">>> %s %s", request.method, request.url.path)
        response = await call_next(request)
        logger.info("<<< %s %s -> %s", request.method, request.url.path, response.status_code)
        return response

    # Mount our UI-facing routes onto the A2A app
    a2a_app.add_middleware(CORSMiddleware, allow_origins=_allowed_origins, allow_methods=["*"], allow_headers=["*"])

    # Add our custom endpoints to the A2A app
    for route in app.routes:
        a2a_app.routes.append(route)

    logger.info("Wealth Management Chat Router serving on :%s", PORT)
    logger.info("  POST /chat         — sync JSON (backward compat)")
    logger.info("  GET  /chat/stream  — SSE streaming")
    logger.info("  POST /             — A2A protocol")

    uvicorn.run(a2a_app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    serve()
