"""Neptune Analytics MCP Server — exposes graph query tools for AgentCore agents."""

import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="NeptuneAnalytics",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
    stateless_http=True,
)


def _get_client():
    from wealth_management_portal_neptune_analytics_core import NeptuneAnalyticsClient

    if not hasattr(_get_client, "_instance"):
        _get_client._instance = NeptuneAnalyticsClient()
    return _get_client._instance


@mcp.tool(description="Execute a raw openCypher query against Neptune Analytics.")
def execute_cypher(query: str) -> dict[str, Any]:
    """Execute an openCypher query and return raw results."""
    return _get_client().execute_query(query)


@mcp.tool(description="Test the connection to Neptune Analytics.")
def test_connection() -> dict[str, Any]:
    """Verify that Neptune Analytics is reachable."""
    client = _get_client()
    ok = client.test_connection()
    return {"connected": ok, "graph_id": client.graph_id, "region": client.region}


@mcp.tool(
    description=(
        "Find similar clients using Neptune graph similarity algorithms. Algorithms: jaccard, overlap, common, total."
    )
)
def find_similar_clients(
    client_id: str,
    algorithm: str = "jaccard",
    min_score: float = 0.0,
    limit: int = 10,
) -> dict[str, Any]:
    """Find similar clients using Neptune graph similarity algorithms."""
    algo_map = {
        "jaccard": "neptune.algo.jaccardSimilarity",
        "overlap": "neptune.algo.overlapSimilarity",
        "common": "neptune.algo.neighbors.common",
        "total": "neptune.algo.neighbors.total",
    }
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


@mcp.tool(description="Compute degree centrality for a list of node IDs.")
def compute_degree_centrality(node_ids: list[str]) -> dict[str, int]:
    """Compute degree centrality (connection count) for given nodes."""
    client = _get_client()
    if not node_ids:
        return {}
    ids_str = ", ".join(f"'{nid}'" for nid in node_ids[:20])
    result: dict[str, int] = {nid: 0 for nid in node_ids[:20]}
    try:
        r = client.execute_query(
            f"MATCH (n) WHERE id(n) IN [{ids_str}] MATCH (n)-[r]-() RETURN id(n) AS nid, count(r) AS degree"
        )
        for row in r.get("results", []):
            nid = row.get("nid")
            if nid in result:
                result[nid] = row.get("degree", 0)
    except Exception as e:
        logger.warning(f"Batched degree centrality failed: {e}")
    return result
