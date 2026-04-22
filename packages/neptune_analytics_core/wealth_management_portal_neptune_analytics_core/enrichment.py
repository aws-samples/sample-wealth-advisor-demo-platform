"""Search results enrichment for Neptune Analytics."""

import logging
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from .client import GRAPH_CONFIG, NeptuneAnalyticsClient, sanitize_cypher_ids, sanitize_cypher_str

logger = logging.getLogger(__name__)

# Columns displayed per node type — sourced from graph_config.yaml (column_strategy)
# with a hardcoded fallback for safety.
_FALLBACK_COLUMNS_BY_TYPE: dict[str, list[str]] = {
    "Client": ["name", "portfolio_value", "net_worth", "job_title", "return_ytd", "holdings", "connections_summary"],
    "Advisor": ["name", "clients", "connections_summary"],
    "Company": ["name", "connections_summary"],
    "Stock": ["name", "connections_summary"],
    "City": ["name", "state", "connections_summary"],
    "RiskProfile": ["level", "connections_summary"],
}

_COLUMNS_BY_TYPE: dict[str, list[str]] = GRAPH_CONFIG.get("column_strategy", {}) or _FALLBACK_COLUMNS_BY_TYPE

_BASE_COLUMNS: list[str] = ["name", "type"]


def get_display_columns(node_type: str) -> list[str]:
    """Return the list of display columns for a given node type."""
    if node_type in _COLUMNS_BY_TYPE:
        type_columns = _COLUMNS_BY_TYPE[node_type]
        columns: list[str] = []
        for col in _BASE_COLUMNS:
            if col not in columns:
                columns.append(col)
        for col in type_columns:
            if col not in columns:
                columns.append(col)
        return columns
    return list(_BASE_COLUMNS)


@dataclass
class RelatedNode:
    """A node related to a matched node via a graph edge."""

    node_id: str
    node_label: str
    node_type: str
    relationship_type: str


@dataclass
class EnrichedNode:
    """Enriched node with full properties and relationships."""

    node_id: str
    node_label: str
    node_type: str
    properties: dict[str, Any] = dataclass_field(default_factory=dict)
    related_nodes: list[RelatedNode] = dataclass_field(default_factory=list)


class SearchResultsEnricher:
    """Collects full node properties and related node information for matched node IDs."""

    def enrich(
        self,
        matching_ids: list[str],
        graph_data: dict[str, Any],
    ) -> list[EnrichedNode]:
        """Look up each matching ID in graph_data, collect properties and related nodes."""
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        node_map: dict[str, dict[str, Any]] = {}
        for node in nodes:
            node_id = node.get("id")
            if node_id is not None:
                node_map[str(node_id)] = node

        # Build adjacency index once — O(E) instead of O(E × N)
        adj: dict[str, list[tuple[str, str]]] = {}
        for edge in edges:
            source = str(edge.get("source", ""))
            target = str(edge.get("target", ""))
            rel_type = str(edge.get("label", ""))
            if source:
                adj.setdefault(source, []).append((target, rel_type))
            if target:
                adj.setdefault(target, []).append((source, rel_type))

        enriched_results: list[EnrichedNode] = []

        for mid in matching_ids:
            mid_str = str(mid)
            node_data = node_map.get(mid_str)
            if node_data is None:
                continue

            properties = dict(node_data.get("properties", {}))
            node_label = str(node_data.get("label", ""))
            node_type = str(node_data.get("type", "")) or node_label

            related_nodes = [
                RelatedNode(
                    node_id=other_id,
                    node_label=str(rn.get("label", "")),
                    node_type=str(rn.get("type", "")) or str(rn.get("label", "")),
                    relationship_type=rel_type,
                )
                for other_id, rel_type in adj.get(mid_str, [])
                if (rn := node_map.get(other_id)) is not None
            ]

            enriched_results.append(
                EnrichedNode(
                    node_id=mid_str,
                    node_label=node_label,
                    node_type=node_type,
                    properties=properties,
                    related_nodes=related_nodes,
                )
            )

        return enriched_results


# ── Connection Breakdown ─────────────────────────────────────────────────────


def _extract_node_label(node_data: dict, node_type: str) -> str:
    """Extract a human-readable label from a graph node."""
    props = node_data.get("~properties", {})
    if node_type in ("Client", "Advisor"):
        return f"{props.get('first_name', '')} {props.get('last_name', '')}".strip()
    if node_type == "Stock":
        return props.get("ticker", "")
    if node_type == "City":
        return f"{props.get('name', '')}, {props.get('state', '')}".strip(", ")
    if node_type == "RiskProfile":
        return props.get("level", "")
    return props.get("name", "") or props.get("label", "")


def compute_connection_breakdown(
    node_ids: list[str],
    neptune_client: NeptuneAnalyticsClient,
    relevant_relationships: list[str] | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Get readable connection details for each node — batched into 2 queries total."""
    breakdown: dict[str, dict[str, list[str]]] = {nid: {} for nid in node_ids}
    if not node_ids:
        return breakdown

    safe_ids = sanitize_cypher_ids(node_ids)
    if not safe_ids:
        return breakdown

    ids_str = ", ".join(f"'{nid}'" for nid in safe_ids)
    rel_filter = ""
    if relevant_relationships:
        allowed = [sanitize_cypher_str(r.upper()) for r in relevant_relationships]
        rel_filter = " AND type(r) IN [" + ", ".join(f"'{r}'" for r in allowed) + "]"

    # Outgoing connections — single batched query
    try:
        out_result = neptune_client.execute_query(
            f"MATCH (n) WHERE id(n) IN [{ids_str}] "
            f"MATCH (n)-[r]->(m) {'WHERE true' + rel_filter if rel_filter else ''} "
            f"RETURN id(n) as nid, type(r) as rel_type, labels(m)[0] as node_type, m as node"
        )
        for row in out_result.get("results", []):
            nid = row.get("nid")
            if nid not in breakdown:
                continue
            label = _extract_node_label(row.get("node", {}), row.get("node_type", ""))
            if label:
                key = row.get("rel_type", "UNKNOWN").replace("_", " ").title()
                breakdown[nid].setdefault(key, []).append(label)
    except Exception as e:
        logger.warning(f"Batched outgoing connection breakdown failed: {e}")

    # Incoming connections — single batched query
    try:
        in_result = neptune_client.execute_query(
            f"MATCH (n) WHERE id(n) IN [{ids_str}] "
            f"MATCH (m)-[r]->(n) {'WHERE true' + rel_filter if rel_filter else ''} "
            f"RETURN id(n) as nid, type(r) as rel_type, labels(m)[0] as node_type, m as node"
        )
        for row in in_result.get("results", []):
            nid = row.get("nid")
            if nid not in breakdown:
                continue
            node_type = row.get("node_type", "")
            label = _extract_node_label(row.get("node", {}), node_type)
            if label:
                rel = row.get("rel_type", "UNKNOWN").replace("_", " ").title()
                key = f"{rel} By" if node_type == "Advisor" else rel
                breakdown[nid].setdefault(key, []).append(label)
    except Exception as e:
        logger.warning(f"Batched incoming connection breakdown failed: {e}")

    return breakdown
