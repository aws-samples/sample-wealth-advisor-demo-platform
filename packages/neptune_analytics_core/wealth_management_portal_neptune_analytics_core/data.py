"""Graph data loading and query functions."""

import logging
from typing import Any

from .client import NeptuneAnalyticsClient, sanitize_cypher_str

logger = logging.getLogger(__name__)


def _esc(val: str) -> str:
    """Escape single quotes for safe Cypher string interpolation."""
    return sanitize_cypher_str(val)


# Data Loading
SAMPLE_DATA = [
    {
        "advisor_id": 1,
        "advisor_first_name": "Jane",
        "advisor_last_name": "Smith",
        "client_id": 1001,
        "first_name": "John",
        "last_name": "Doe",
        "portfolio_value": 500000,
        "net_worth": 1500000,
        "employer": "Tech Corp",
        "job_title": "Software Engineer",
        "city": "San Francisco",
        "state": "CA",
        "holdings": "AAPL,GOOGL",
        "risk_tolerance": "Moderate",
    },
    {
        "advisor_id": 1,
        "advisor_first_name": "Jane",
        "advisor_last_name": "Smith",
        "client_id": 1002,
        "first_name": "Sarah",
        "last_name": "Williams",
        "portfolio_value": 750000,
        "net_worth": 2000000,
        "employer": "Finance Inc",
        "job_title": "CFO",
        "city": "New York",
        "state": "NY",
        "holdings": "MSFT,AMZN",
        "risk_tolerance": "Aggressive",
    },
    {
        "advisor_id": 2,
        "advisor_first_name": "Michael",
        "advisor_last_name": "Johnson",
        "client_id": 1003,
        "first_name": "Robert",
        "last_name": "Brown",
        "portfolio_value": 320000,
        "net_worth": 800000,
        "employer": "Health Plus",
        "job_title": "Doctor",
        "city": "Seattle",
        "state": "WA",
        "holdings": "AAPL,MSFT",
        "risk_tolerance": "Conservative",
    },
    {
        "advisor_id": 2,
        "advisor_first_name": "Michael",
        "advisor_last_name": "Johnson",
        "client_id": 1004,
        "first_name": "Emily",
        "last_name": "Davis",
        "portfolio_value": 1200000,
        "net_worth": 3500000,
        "employer": "Tech Corp",
        "job_title": "VP Engineering",
        "city": "San Francisco",
        "state": "CA",
        "holdings": "GOOGL,AMZN",
        "risk_tolerance": "Aggressive",
    },
]


def load_sample_data(client: NeptuneAnalyticsClient) -> dict[str, int]:
    """Load sample financial advisor data into Neptune Analytics."""
    stats = {
        "advisors_created": 0,
        "clients_created": 0,
        "companies_created": 0,
        "cities_created": 0,
        "stocks_created": 0,
        "risk_profiles_created": 0,
        "edges_created": 0,
        "errors": 0,
    }
    seen = {"advisors": set(), "companies": set(), "cities": set(), "stocks": set(), "risk_profiles": set()}

    for rec in SAMPLE_DATA:
        try:
            aid, cid = rec["advisor_id"], rec["client_id"]

            # Advisor
            if aid not in seen["advisors"]:
                client.execute_query(
                    f"MERGE (a:Advisor {{advisor_id: {aid}}}) "
                    f"SET a.first_name = '{_esc(rec['advisor_first_name'])}', "
                    f"a.last_name = '{_esc(rec['advisor_last_name'])}'"
                )
                seen["advisors"].add(aid)
                stats["advisors_created"] += 1

            # Client
            client.execute_query(
                f"MERGE (c:Client {{client_id: {cid}}}) "
                f"SET c.first_name = '{_esc(rec['first_name'])}', "
                f"c.last_name = '{_esc(rec['last_name'])}', "
                f"c.portfolio_value = {rec['portfolio_value']}, "
                f"c.net_worth = {rec['net_worth']}, "
                f"c.job_title = '{_esc(rec['job_title'])}'"
            )
            stats["clients_created"] += 1

            # MANAGES edge
            client.execute_query(
                f"MATCH (a:Advisor {{advisor_id: {aid}}}), (c:Client {{client_id: {cid}}}) MERGE (a)-[:MANAGES]->(c)"
            )
            stats["edges_created"] += 1

            # Company
            company = rec["employer"]
            if company not in seen["companies"]:
                client.execute_query(f"MERGE (co:Company {{name: '{_esc(company)}'}})")
                seen["companies"].add(company)
                stats["companies_created"] += 1
            client.execute_query(
                f"MATCH (c:Client {{client_id: {cid}}}), (co:Company {{name: '{_esc(company)}'}})"
                " MERGE (c)-[:WORKS_AT]->(co)"
            )
            stats["edges_created"] += 1

            # City
            city, state = rec["city"], rec["state"]
            city_key = f"{city}_{state}"
            if city_key not in seen["cities"]:
                client.execute_query(f"MERGE (ci:City {{name: '{_esc(city)}', state: '{_esc(state)}'}})")
                seen["cities"].add(city_key)
                stats["cities_created"] += 1
            client.execute_query(
                f"MATCH (c:Client {{client_id: {cid}}}), "
                f"(ci:City {{name: '{_esc(city)}', state: '{_esc(state)}'}}) "
                f"MERGE (c)-[:LIVES_IN]->(ci)"
            )
            stats["edges_created"] += 1

            # Stocks
            for ticker in (rec.get("holdings") or "").split(","):
                ticker = ticker.strip().upper()
                if not ticker:
                    continue
                if ticker not in seen["stocks"]:
                    client.execute_query(f"MERGE (s:Stock {{ticker: '{ticker}'}})")
                    seen["stocks"].add(ticker)
                    stats["stocks_created"] += 1
                client.execute_query(
                    f"MATCH (c:Client {{client_id: {cid}}}), (s:Stock {{ticker: '{ticker}'}}) MERGE (c)-[:HOLDS]->(s)"
                )
                stats["edges_created"] += 1

            # RiskProfile
            risk = rec.get("risk_tolerance", "")
            if risk:
                if risk not in seen["risk_profiles"]:
                    client.execute_query(f"MERGE (r:RiskProfile {{level: '{_esc(risk)}'}})")
                    seen["risk_profiles"].add(risk)
                    stats["risk_profiles_created"] += 1
                client.execute_query(
                    f"MATCH (c:Client {{client_id: {cid}}}), "
                    f"(r:RiskProfile {{level: '{_esc(risk)}'}}) "
                    f"MERGE (c)-[:HAS_RISK_PROFILE]->(r)"
                )
                stats["edges_created"] += 1
        except Exception as e:
            logger.warning(f"Error processing record: {e}")
            stats["errors"] += 1
    return stats


# Query Functions
NODE_TYPES = ("Advisor", "Client", "Company", "City", "Stock", "RiskProfile")


def _get_node_label(node_type: str, props: dict, node_id: str) -> str:
    """Generate display label for a node."""
    if node_type in ("Advisor", "Client"):
        return (
            f"{props.get('first_name', '')} {props.get('last_name', '')}".strip()
            or f"{node_type} {props.get('advisor_id', props.get('client_id', ''))}"
        )
    if node_type == "City":
        return f"{props.get('name', '')}, {props.get('state', '')}".strip(", ")
    return props.get("name") or props.get("ticker") or props.get("level") or props.get("label") or node_id


def get_all_nodes(client: NeptuneAnalyticsClient, limit: int = 5000) -> list[dict[str, Any]]:
    """Get all nodes from the graph (excluding transaction data)."""
    query = f"MATCH (n) WHERE {' OR '.join(f'n:{t}' for t in NODE_TYPES)} RETURN n LIMIT {limit}"
    results = client.execute_query(query).get("results", [])

    nodes = []
    for result in results:
        node_data = result.get("n", {})
        if not node_data:
            continue
        node_id = node_data.get("~id", "")
        labels = node_data.get("~labels", [])
        props = {k: v for k, v in node_data.items() if not k.startswith("~")}
        props.update(node_data.get("~properties", {}))
        node_type = labels[0] if labels else "Unknown"
        nodes.append(
            {"id": node_id, "type": node_type, "label": _get_node_label(node_type, props, node_id), "properties": props}
        )
    return nodes


def get_all_edges(client: NeptuneAnalyticsClient, limit: int = 10000) -> list[dict[str, Any]]:
    """Get all edges from the graph (excluding transaction data)."""
    type_filter = " OR ".join(f"a:{t}" for t in NODE_TYPES)
    query = (
        f"MATCH (a)-[r]->(b) WHERE ({type_filter}) AND ({type_filter.replace('a:', 'b:')}) RETURN a, r, b LIMIT {limit}"
    )
    results = client.execute_query(query).get("results", [])

    return [
        {
            "source_id": r.get("a", {}).get("~id", ""),
            "target_id": r.get("b", {}).get("~id", ""),
            "type": r.get("r", {}).get("~type", "RELATED"),
        }
        for r in results
        if r.get("a") and r.get("r") and r.get("b")
    ]


def get_graph_data(client: NeptuneAnalyticsClient, limit: int = 5000) -> dict[str, Any]:
    """Get complete graph data (nodes and edges) for visualization."""
    return {"nodes": get_all_nodes(client, limit), "edges": get_all_edges(client, limit * 2)}
