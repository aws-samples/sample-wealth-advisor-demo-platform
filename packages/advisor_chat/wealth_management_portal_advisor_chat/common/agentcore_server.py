"""Shared helper to add AgentCore HTTP-protocol endpoints to an A2A server.

AgentCore with ProtocolType.HTTP expects:
- GET /ping         — health check
- POST /invocations — request handler
The A2A server already handles POST / and GET /.well-known/agent.json.
"""

import asyncio
import json
import logging
import re

import uvicorn
from fastapi import Query, Request
from fastapi.responses import StreamingResponse
from strands.multiagent.a2a import A2AServer

from .streaming import done_event, error_event, status_event, token_event

logger = logging.getLogger(__name__)


def _strip_thinking(text: str) -> str:
    return re.sub(r"<thinking>[\s\S]*?</thinking>\s*", "", text).strip()


def serve_agent(agent_factory, name: str, port: int):
    """Start an A2A server with AgentCore /ping and /invocations added."""
    agent = agent_factory()
    a2a_server = A2AServer(agent=agent, host="0.0.0.0", port=port)
    app = a2a_server.to_fastapi_app()

    @app.get("/ping")
    def ping():
        return ""

    def _parse_invocation_text(payload: dict) -> str:
        for part in payload.get("params", {}).get("message", {}).get("parts", []):
            if part.get("kind") == "text":
                return part.get("text", "")
        return ""

    @app.post("/invocations")
    async def invocations(request: Request):
        body = await request.body()
        logger.info("[%s] Invocation received (%d bytes)", name, len(body))
        payload = json.loads(body)

        text = _parse_invocation_text(payload)
        if not text:
            return {"jsonrpc": "2.0", "id": payload.get("id", 1), "error": {"code": -32600, "message": "No text found"}}

        accept = request.headers.get("accept", "")
        session_id = payload.get("params", {}).get("message", {}).get("messageId", "")

        # SSE streaming path — per AgentCore HTTP protocol contract
        if "text/event-stream" in accept:

            async def sse_generator():
                try:
                    a = agent_factory(session_id=session_id) if session_id else agent_factory()
                    async for event in a.stream_async(text):
                        if "data" in event:
                            yield token_event(event["data"])
                        elif "current_tool_use" in event:
                            tool = event["current_tool_use"].get("name", "")
                            if tool:
                                yield status_event(f"{tool}...")
                        elif "result" in event:
                            reply = str(event["result"]) if event["result"] else "No response."
                            yield done_event(_strip_thinking(reply))
                except Exception as e:
                    logger.exception("[%s] SSE invocation error", name)
                    yield error_event(str(e))

            return StreamingResponse(sse_generator(), media_type="text/event-stream")

        # JSON path — existing behavior
        try:
            a = agent_factory(session_id=session_id) if session_id else agent_factory()
            result = await asyncio.to_thread(a, text)
            reply = str(result) if result else "No response."
            reply = _strip_thinking(reply)
        except Exception as e:
            logger.exception("[%s] Invocation error", name)
            reply = f"Error: {e}"

        return {
            "jsonrpc": "2.0",
            "id": payload.get("id", 1),
            "result": {"artifacts": [{"parts": [{"kind": "text", "text": reply}]}]},
        }

    @app.get("/stream")
    async def stream(message: str = Query(...), session_id: str = Query("")):
        """SSE streaming endpoint — streams tokens and tool status from this agent."""

        async def event_generator():
            try:
                queue: asyncio.Queue = asyncio.Queue()

                def cb(**kwargs):
                    data = kwargs.get("data", "")
                    if data:
                        queue.put_nowait(("token", data))

                from strands.hooks import HookProvider, HookRegistry
                from strands.hooks.events import AfterToolCallEvent, BeforeToolCallEvent

                class _Hooks(HookProvider):
                    def register_hooks(self, registry: HookRegistry) -> None:
                        registry.add_callback(BeforeToolCallEvent, self._before)
                        registry.add_callback(AfterToolCallEvent, self._after)

                    def _before(self, event: BeforeToolCallEvent) -> None:
                        tool = event.tool_use.get("name", "")
                        queue.put_nowait(("status", f"{tool}..."))

                    def _after(self, event: AfterToolCallEvent) -> None:
                        tool = event.tool_use.get("name", "")
                        queue.put_nowait(("status", f"{tool} ✓"))

                a = agent_factory(session_id=session_id) if session_id else agent_factory()
                a.callback_handler = cb
                a.hooks = [_Hooks()]

                loop = asyncio.get_event_loop()
                task = loop.run_in_executor(None, a, message)

                while True:
                    while not queue.empty():
                        kind, payload = queue.get_nowait()
                        yield token_event(payload) if kind == "token" else status_event(payload)
                    if task.done():
                        break
                    await asyncio.sleep(0.05)

                while not queue.empty():
                    kind, payload = queue.get_nowait()
                    yield token_event(payload) if kind == "token" else status_event(payload)

                result = task.result()
                text = str(result) if result else "No response."
                text = _strip_thinking(text)
                yield done_event(text)

            except Exception as e:
                logger.exception("[%s] Stream error", name)
                yield error_event(str(e))

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    logger.info("%s serving on :%s", name, port)
    uvicorn.run(app, host="0.0.0.0", port=port)
