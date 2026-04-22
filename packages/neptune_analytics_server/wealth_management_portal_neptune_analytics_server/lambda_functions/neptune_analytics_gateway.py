"""Neptune Analytics Gateway Lambda handler — routes AgentCore Gateway tool calls."""

import logging

from wealth_management_portal_neptune_analytics_core import NeptuneAnalyticsClient

logger = logging.getLogger(__name__)

_client: NeptuneAnalyticsClient | None = None


def _get_client() -> NeptuneAnalyticsClient:
    global _client
    if _client is None:
        _client = NeptuneAnalyticsClient()
    return _client


def _execute_cypher(event: dict) -> dict:
    return _get_client().execute_query(event["query"])


def _test_connection(event: dict) -> dict:
    client = _get_client()
    ok = client.test_connection()
    return {"connected": ok, "graph_id": client.graph_id, "region": client.region}


def _find_similar_clients(event: dict) -> dict:
    algo_map = {
        "jaccard": "neptune.algo.jaccardSimilarity",
        "overlap": "neptune.algo.overlapSimilarity",
        "common": "neptune.algo.neighbors.common",
        "total": "neptune.algo.neighbors.total",
    }
    client_id = event["client_id"]
    algorithm = event.get("algorithm", "jaccard")
    min_score = event.get("min_score", 0.0)
    limit = event.get("limit", 10)
    algo_func = algo_map.get(algorithm, algo_map["jaccard"])
    cypher = f"""
    MATCH (c:Client {{`~id`: '{client_id}'}})
    CALL {algo_func}(c, {{topK: {limit}}})
    YIELD node, score
    WHERE score > {min_score}
    RETURN node.`~id` AS id, node.first_name AS first_name,
           node.last_name AS last_name, score
    ORDER BY score DESC LIMIT {limit}
    """
    return _get_client().execute_query(cypher)


def _compute_degree_centrality(event: dict) -> dict:
    node_ids = event["node_ids"]
    if not node_ids:
        return {}
    ids_str = ", ".join(f"'{nid}'" for nid in node_ids[:20])
    result: dict = {nid: 0 for nid in node_ids[:20]}
    try:
        r = _get_client().execute_query(
            f"MATCH (n) WHERE id(n) IN [{ids_str}] MATCH (n)-[r]-() RETURN id(n) AS nid, count(r) AS degree"
        )
        for row in r.get("results", []):
            nid = row.get("nid")
            if nid in result:
                result[nid] = row.get("degree", 0)
    except Exception as e:
        logger.warning("Batched degree centrality failed: %s", e)
    return result


TOOL_HANDLERS = {
    "execute_cypher": _execute_cypher,
    "test_connection": _test_connection,
    "find_similar_clients": _find_similar_clients,
    "compute_degree_centrality": _compute_degree_centrality,
}


def lambda_handler(event: dict, context) -> dict:
    full_name = context.client_context.custom.get("bedrockAgentCoreToolName", "")
    parts = full_name.split("___")
    tool_name = parts[-1] if len(parts) > 1 else full_name
    if not tool_name:
        raise ValueError(f"Missing or invalid tool name: {context.client_context.custom}")
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        raise ValueError(f"Unknown tool: {tool_name}. Available: {list(TOOL_HANDLERS)}")
    return handler(event)
