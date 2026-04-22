import asyncio
import json
import logging
import queue
import threading

import uvicorn
from bedrock_agentcore.runtime.models import PingStatus
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from wealth_management_portal_neptune_analytics_core import get_neptune_client

from ..neptune_analytics import get_nl_search_engine
from .agent import _get_query_client
from .init import app

logger = logging.getLogger(__name__)


@app.post("/invocations")
async def invoke(request: Request):
    """Entry point for agent invocation — returns structured JSON or SSE stream."""
    body = await request.body()
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("latin-1")
    data = json.loads(text) if text else {}
    query = data.get("query", "")
    if not query:
        return JSONResponse({"matching_ids": [], "explanation": "No query provided", "node_metrics": {}})

    accept = request.headers.get("accept", "")

    # SSE streaming path — when AgentCore or browser sends Accept: text/event-stream
    if "text/event-stream" in accept:
        status_q: queue.Queue = queue.Queue()

        def _run_stream():
            try:
                engine = get_nl_search_engine()
                neptune_client = _get_query_client()
                direct_client = get_neptune_client()
                result = engine.search(
                    query,
                    neptune_client,
                    direct_client=direct_client,
                    on_status=lambda step, msg: status_q.put(("status", {"step": step, "message": msg})),
                    on_token=lambda t: status_q.put(("token", {"text": t})),
                    on_match=lambda ids: status_q.put(("match", {"matching_ids": ids})),
                )
                status_q.put(("result", json.loads(json.dumps(result, default=str))))
            except Exception as e:
                logger.error(f"SSE invocation failed: {e}")
                status_q.put(("result", {"matching_ids": [], "explanation": str(e), "node_metrics": {}}))
            status_q.put(None)

        threading.Thread(target=_run_stream, daemon=True).start()

        async def sse_generator():
            while True:
                try:
                    item = status_q.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.05)
                    continue
                if item is None:
                    break
                event_type, payload = item
                yield f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    # JSON path — existing behavior
    try:
        engine = get_nl_search_engine()
        neptune_client = _get_query_client()
        direct_client = get_neptune_client()
        result = engine.search(query, neptune_client, direct_client=direct_client)
        return JSONResponse(json.loads(json.dumps(result, default=str)))
    except Exception as e:
        logger.error(f"Invocation failed: {e}")
        return JSONResponse(
            {
                "matching_ids": [],
                "explanation": f"Search failed: {e}",
                "reasoning": "",
                "node_metrics": {},
                "error": str(e),
            },
            status_code=500,
        )


@app.post("/invocations/stream")
async def invoke_stream(request: Request):
    """SSE streaming invocation — emits status events from engine.search(), then the result."""
    body = await request.body()
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("latin-1")
    data = json.loads(text) if text else {}
    query = data.get("query", "")
    if not query:
        return StreamingResponse(iter([]), media_type="text/event-stream")

    status_q: queue.Queue = queue.Queue()

    def _run():
        try:
            engine = get_nl_search_engine()
            neptune_client = _get_query_client()
            direct_client = get_neptune_client()
            result = engine.search(
                query,
                neptune_client,
                direct_client=direct_client,
                on_status=lambda step, msg: status_q.put(("status", {"step": step, "message": msg})),
                on_token=lambda text: status_q.put(("token", {"text": text})),
                on_match=lambda ids: status_q.put(("match", {"matching_ids": ids})),
            )
            status_q.put(("result", json.loads(json.dumps(result, default=str))))
        except Exception as e:
            logger.error(f"Stream invocation failed: {e}")
            status_q.put(("result", {"matching_ids": [], "explanation": str(e), "node_metrics": {}}))
        status_q.put(None)

    threading.Thread(target=_run, daemon=True).start()

    async def event_generator():
        while True:
            try:
                item = status_q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue
            if item is None:
                break
            event_type, payload = item
            yield f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/ping")
def ping() -> str:
    # TODO: if running an async task, return PingStatus.HEALTHY_BUSY
    return PingStatus.HEALTHY


if __name__ == "__main__":
    uvicorn.run("wealth_management_portal_graph_search_engine.graph_search_agent.main:app", port=8080)
