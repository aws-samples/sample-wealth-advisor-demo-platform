"""Graph Search API — FastAPI endpoints for Neptune Analytics graph search."""

import asyncio
import concurrent.futures
import json
import logging
import os
import queue
import threading
import uuid
from typing import Any

import boto3
import botocore.config
import httpx
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from wealth_management_portal_neptune_analytics_core import (
    DEFAULT_NODE_LIMIT,
    GRAPH_CONFIG,
    MAX_NODE_LIMIT,
    ColumnExplainer,
    SearchResultsEnricher,
    compute_connection_breakdown,
    get_display_columns,
    get_graph_data,
    get_neptune_client,
    load_sample_data,
)

from .init import app, lambda_handler, tracer

handler = lambda_handler
logger = logging.getLogger(__name__)

STALE_METRIC_PROPS = {"centrality", "degree", "closeness", "pageRank", "pagerank", "betweenness"}
GRAPH_SEARCH_AGENT_URL = os.environ.get("GRAPH_SEARCH_AGENT_URL", "")
GRAPH_SEARCH_AGENT_ARN = os.environ.get("GRAPH_SEARCH_AGENT_ARN", "")


# ── Response Models ──────────────────────────────────────────────────────────


class NodeResponse(BaseModel):
    id: str
    type: str
    label: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)


class EdgeResponse(BaseModel):
    source_id: str
    target_id: str
    type: str


class GraphDataResponse(BaseModel):
    nodes: list[NodeResponse] = Field(default_factory=list)
    edges: list[EdgeResponse] = Field(default_factory=list)


class RelatedNodeEnrichedResponse(BaseModel):
    node_id: str
    node_label: str
    node_type: str
    relationship_type: str


class EnrichedNodeResponse(BaseModel):
    node_id: str
    node_label: str
    node_type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    related_nodes: list[RelatedNodeEnrichedResponse] = Field(default_factory=list)


class EnrichedSearchRequest(BaseModel):
    model_config = {"extra": "ignore"}
    query: str = Field(..., description="Natural language search query")
    graph_data: dict[str, Any] = Field(default_factory=dict)


class EnrichedSearchResponse(BaseModel):
    matching_ids: list[str] = Field(default_factory=list)
    enriched_nodes: list[EnrichedNodeResponse] = Field(default_factory=list)
    column_explanations: dict[str, str] = Field(default_factory=dict)
    explanation: str = ""
    reasoning: str = ""
    node_metrics: dict[str, Any] = Field(default_factory=dict)


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/api/config")
@tracer.capture_method
def get_config():
    """Return client-facing configuration."""
    return {"default_node_limit": DEFAULT_NODE_LIMIT, "max_node_limit": MAX_NODE_LIMIT, **GRAPH_CONFIG}


@app.get("/api/graph", response_model=GraphDataResponse)
@tracer.capture_method
def get_graph(limit: int = DEFAULT_NODE_LIMIT):
    data = get_graph_data(get_neptune_client(), limit)
    return GraphDataResponse(
        nodes=[NodeResponse(**n) for n in data["nodes"]],
        edges=[EdgeResponse(**e) for e in data["edges"]],
    )


@app.post("/api/graph/load")
@tracer.capture_method
def load_data():
    return load_sample_data(get_neptune_client())


# ── Enriched Search ──────────────────────────────────────────────────────────


def _enrich_and_finalize(query, search_result, graph_data, dc):
    """Shared enrichment: backfill connections + explain columns in parallel."""
    matching_ids = search_result.get("matching_ids", [])
    node_metrics = search_result.get("node_metrics", {})

    enriched_nodes = []
    logger.info(
        f"Enrichment: matching_ids={len(matching_ids)}, "
        f"graph_data nodes={len(graph_data.get('nodes', [])) if graph_data else 0}"
    )
    if matching_ids and graph_data:
        try:
            enriched = SearchResultsEnricher().enrich(matching_ids, graph_data)
            enriched_nodes = [
                EnrichedNodeResponse(
                    node_id=n.node_id,
                    node_label=n.node_label,
                    node_type=n.node_type,
                    properties={k: v for k, v in n.properties.items() if k not in STALE_METRIC_PROPS},
                    related_nodes=[
                        RelatedNodeEnrichedResponse(
                            node_id=rn.node_id,
                            node_label=rn.node_label,
                            node_type=rn.node_type,
                            relationship_type=rn.relationship_type,
                        )
                        for rn in n.related_nodes
                    ],
                )
                for n in enriched
            ]
        except Exception as e:
            logger.warning(f"Enrichment failed: {e}")

    def _backfill():
        if not matching_ids:
            return
        try:
            # Only backfill nodes that truly have no connections —
            # the engine's search() already computes connection breakdown,
            # so this only fires for the direct-AgentCore path or edge cases.
            missing = [
                nid
                for nid in matching_ids[:20]
                if nid not in node_metrics or not node_metrics.get(nid, {}).get("connections")
            ]
            if not missing:
                return
            relevant_rels = search_result.get("relevant_relationships")
            breakdown = compute_connection_breakdown(missing, dc, relevant_rels)
            for nid in missing:
                node_metrics.setdefault(nid, {})["connections"] = breakdown.get(nid, {})
        except Exception as e:
            logger.warning(f"Connection backfill failed: {e}")

    def _explain_columns():
        if not enriched_nodes:
            return {}
        try:
            types = [n.node_type for n in enriched_nodes]
            predominant = max(set(types), key=types.count) if types else "Mixed"
            return ColumnExplainer().explain(get_display_columns(predominant))
        except Exception:
            return {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        bf = pool.submit(_backfill)
        cf = pool.submit(_explain_columns)
        bf.result()
        column_explanations = cf.result()

    return EnrichedSearchResponse(
        matching_ids=[str(mid) for mid in matching_ids],
        enriched_nodes=enriched_nodes,
        column_explanations=column_explanations,
        explanation=search_result.get("explanation", ""),
        reasoning=search_result.get("reasoning", ""),
        node_metrics=node_metrics,
    )


# ── Enrichment-only endpoint (called after UI invokes AgentCore directly) ──


class EnrichRequest(BaseModel):
    model_config = {"extra": "ignore"}
    query: str
    search_result: dict[str, Any] = Field(default_factory=dict)
    graph_data: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/enrich", response_model=EnrichedSearchResponse)
@tracer.capture_method
def enrich(request: EnrichRequest):
    """Fast enrichment: backfill connections + explain columns. No agent call."""
    dc = get_neptune_client()
    return _enrich_and_finalize(request.query, request.search_result, request.graph_data, dc)


# ── SSE Streaming Search ────────────────────────────────────────────────────


def _stream_from_agent_local(agent_url: str, query: str, graph_data: dict, status_q: queue.Queue):
    """Local dev: call agent's /invocations/stream SSE endpoint and forward events."""
    try:
        payload = {"query": query, "graph_data": graph_data}
        with (
            httpx.Client(timeout=180) as http_client,
            http_client.stream("POST", f"{agent_url}/invocations/stream", json=payload) as resp,
        ):
            event_type = ""
            for line in resp.iter_lines():
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
                    if event_type == "status":
                        status_q.put(("status", data))
                    elif event_type == "token":
                        status_q.put(("token", data))
                    elif event_type == "match":
                        status_q.put(("match", data))
                    elif event_type == "result":
                        return data
        return {"matching_ids": [], "explanation": "No result from agent stream"}
    except Exception as e:
        logger.warning(f"Agent stream failed, falling back to non-streaming: {e}")
        # Fallback: call the original non-streaming endpoint
        status_q.put(("status", {"step": "invoke", "message": "🚀 Invoking Graph Search Agent..."}))
        with httpx.Client(timeout=120) as http_client:
            resp = http_client.post(f"{agent_url}/invocations", json={"query": query, "graph_data": graph_data})
            return json.loads(resp.text) if resp.text else {"matching_ids": [], "explanation": "No response"}


def _invoke_agentcore_search(query: str, graph_data: dict, status_q: queue.Queue):
    """Invoke Graph Search Agent on AgentCore for AI search (Flow 2) with SSE streaming."""
    try:
        status_q.put(("status", {"step": "invoke", "message": "🚀 Invoking Graph Search Agent..."}))
        client = boto3.client(
            "bedrock-agentcore",
            config=botocore.config.Config(read_timeout=180),
        )
        session_id = f"graph-search-{uuid.uuid4().hex}"
        payload = json.dumps({"query": query, "graph_data": graph_data})
        response = client.invoke_agent_runtime(
            agentRuntimeArn=GRAPH_SEARCH_AGENT_ARN,
            runtimeSessionId=session_id,
            payload=payload,
            accept="text/event-stream",
        )
        content_type = response.get("contentType", "")

        if "text/event-stream" in content_type:
            # Parse SSE stream from AgentCore
            search_result = None
            event_type = ""
            for raw_line in response["response"].iter_lines(chunk_size=10):
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                if line.startswith("event: "):
                    event_type = line[7:].strip()
                elif line.startswith("data: ") and event_type:
                    try:
                        data = json.loads(line[6:])
                        if event_type == "status":
                            status_q.put(("status", data))
                        elif event_type == "token":
                            status_q.put(("token", data))
                        elif event_type == "result":
                            search_result = data
                    except (ValueError, TypeError):
                        pass
                    event_type = ""

            if not search_result:
                search_result = {"matching_ids": [], "explanation": "No result from agent stream"}
        else:
            # JSON fallback
            result_text = response["response"].read()
            search_result = (
                json.loads(result_text)
                if result_text
                else {"matching_ids": [], "explanation": "No response from agent"}
            )

        status_q.put(("status", {"step": "enrich", "message": "✨ Enriching results..."}))
        dc = get_neptune_client()
        result = _enrich_and_finalize(query, search_result, graph_data, dc)
        status_q.put(("result", result.model_dump()))
    except Exception as e:
        logger.error(f"AgentCore invocation failed: {e}")
        return False
    status_q.put(None)
    return True


@app.post("/api/nl-search-enriched-stream")
async def enriched_search_stream(request: EnrichedSearchRequest):
    """SSE stream with status updates during search, then the final result."""
    if not request.query.strip():
        return StreamingResponse(iter([]), media_type="text/event-stream")

    query = request.query.strip()
    graph_data = request.graph_data
    status_q: queue.Queue = queue.Queue()

    def _run_search():
        try:
            if GRAPH_SEARCH_AGENT_URL:
                # Local dev: stream status events from agent's SSE endpoint
                search_result = _stream_from_agent_local(GRAPH_SEARCH_AGENT_URL, query, graph_data, status_q)
            elif GRAPH_SEARCH_AGENT_ARN:
                # Production: invoke via Bedrock AgentCore
                if _invoke_agentcore_search(query, graph_data, status_q):
                    return
                search_result = {"matching_ids": [], "explanation": "Agent invocation failed"}
            else:
                search_result = {
                    "matching_ids": [],
                    "explanation": "No agent configured (set GRAPH_SEARCH_AGENT_URL or GRAPH_SEARCH_AGENT_ARN)",
                }

            status_q.put(("status", {"step": "enrich", "message": "✨ Enriching results..."}))
            dc = get_neptune_client()
            result = _enrich_and_finalize(query, search_result, graph_data, dc)
            status_q.put(("result", result.model_dump()))
        except Exception as e:
            logger.error(f"Search failed: {e}")
            status_q.put(
                (
                    "result",
                    {
                        "matching_ids": [],
                        "explanation": str(e),
                        "reasoning": "",
                        "enriched_nodes": [],
                        "column_explanations": {},
                        "node_metrics": {},
                    },
                )
            )
        status_q.put(None)

    threading.Thread(target=_run_search, daemon=True).start()

    async def event_generator():
        while True:
            try:
                item = status_q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue
            if item is None:
                break
            event_type, data = item
            yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
