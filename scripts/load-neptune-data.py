#!/usr/bin/env python3
"""
Post-deploy data loader for Neptune Analytics.

Reads the graph ID from SSM Parameter Store (published by CDK), then loads
advisor_client_graph_data.csv into the Neptune Analytics graph using openCypher
MERGE queries via boto3 neptune-graph.

Usage:
    python scripts/load-neptune-data.py [--region us-west-2]
    python scripts/load-neptune-data.py --graph-id g-xxxxxxxxxx

Graph structure:
    Nodes:  Advisor, Client, Company, City, Stock, RiskProfile
    Edges:  MANAGES, WORKS_AT, LIVES_IN, HOLDS, HAS_RISK_PROFILE
"""
import argparse
import csv
import logging
import os
import sys

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

REGION = "us-west-2"
SSM_PARAM = "/wealth-management-portal/neptune-graph-id"
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "neptune", "advisor_client_graph_data.csv")


# ============================================================================
# Resolve Graph ID from SSM Parameter Store
# ============================================================================

def get_graph_id(region: str) -> str:
    """Fetch graph ID from the CDK-managed SSM parameter."""
    ssm = boto3.client("ssm", region_name=region)
    value = ssm.get_parameter(Name=SSM_PARAM)["Parameter"]["Value"]
    logger.info(f"Resolved GraphId from SSM: {value}")
    return value


# ============================================================================
# CSV reader + transform
# ============================================================================

def read_csv(path: str) -> list[dict]:
    """Read CSV and transform records to the graph loader format."""
    records = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            records.append({
                "advisor_id": int(row["advisor_id"]),
                "advisor_first_name": row["advisor_first_name"],
                "advisor_last_name": row["advisor_last_name"],
                "client_id": int(row["client_id"]),
                "first_name": row["client_first_name"],
                "last_name": row["client_last_name"],
                "portfolio_value": float(row["client_total_aum"] or 0),
                "net_worth": float(row["client_net_worth"] or 0),
                "employer": row["client_employer_name"],
                "job_title": row["client_job_title"],
                "city": row["client_city"],
                "state": row["client_state"],
                "holdings": row["holding"],
                "risk_tolerance": row["risk_tolerance_level"],
                "return_ytd": float(row["return_ytd"] or 0),
                "return_1_year": float(row["return_1_year"] or 0),
                "return_3_year": float(row["return_3_year"] or 0),
                "return_inception": float(row["return_inception"] or 0),
                "client_since": row["client_since"],
                "last_meeting": row["last_meeting"],
            })
    logger.info(f"Read {len(records)} records from {path}")
    return records


# ============================================================================
# Neptune graph loader
# ============================================================================

def _escape(value: str) -> str:
    if value is None:
        return ""
    return str(value).replace("'", "\\'")


def execute_query(client, graph_id: str, query: str):
    return client.execute_query(graphIdentifier=graph_id, queryString=query, language="OPEN_CYPHER")


def load_graph_data(graph_id: str, region: str, records: list[dict]) -> dict:
    client = boto3.client("neptune-graph", region_name=region)

    # Test connection
    execute_query(client, graph_id, "RETURN 1 as test")
    logger.info("Neptune connection successful!")

    stats = {"advisors_created": 0, "clients_created": 0, "companies_created": 0,
             "cities_created": 0, "stocks_created": 0, "risk_profiles_created": 0,
             "edges_created": 0, "errors": 0}

    seen_advisors, seen_companies, seen_cities, seen_stocks, seen_risk_profiles = set(), set(), set(), set(), set()

    total = len(records)
    for idx, rec in enumerate(records):
        if idx % 10 == 0:
            logger.info(f"Processing record {idx + 1}/{total}...")
        try:
            aid, cid = rec["advisor_id"], rec["client_id"]

            # Advisor node
            if aid and aid not in seen_advisors:
                execute_query(client, graph_id, f"""
                    MERGE (a:Advisor {{advisor_id: {aid}}})
                    SET a.first_name = '{_escape(rec['advisor_first_name'])}',
                        a.last_name = '{_escape(rec['advisor_last_name'])}'""")
                seen_advisors.add(aid)
                stats["advisors_created"] += 1

            # Client node
            if cid:
                execute_query(client, graph_id, f"""
                    MERGE (c:Client {{client_id: {cid}}})
                    SET c.first_name = '{_escape(rec['first_name'])}',
                        c.last_name = '{_escape(rec['last_name'])}',
                        c.portfolio_value = {rec['portfolio_value']},
                        c.net_worth = {rec['net_worth']},
                        c.job_title = '{_escape(rec['job_title'])}',
                        c.return_ytd = {rec['return_ytd']},
                        c.return_1_year = {rec['return_1_year']},
                        c.return_3_year = {rec['return_3_year']},
                        c.return_inception = {rec['return_inception']},
                        c.client_since = '{_escape(rec['client_since'])}',
                        c.last_meeting = '{_escape(rec['last_meeting'])}'""")
                stats["clients_created"] += 1

                # MANAGES edge
                if aid:
                    execute_query(client, graph_id, f"""
                        MATCH (a:Advisor {{advisor_id: {aid}}})
                        MATCH (c:Client {{client_id: {cid}}})
                        MERGE (a)-[:MANAGES]->(c)""")
                    stats["edges_created"] += 1

            # Company node + WORKS_AT edge
            company = rec.get("employer", "")
            if company:
                if company not in seen_companies:
                    execute_query(client, graph_id, f"MERGE (co:Company {{name: '{_escape(company)}'}})")
                    seen_companies.add(company)
                    stats["companies_created"] += 1
                if cid:
                    execute_query(client, graph_id, f"""
                        MATCH (c:Client {{client_id: {cid}}})
                        MATCH (co:Company {{name: '{_escape(company)}'}})
                        MERGE (c)-[:WORKS_AT]->(co)""")
                    stats["edges_created"] += 1

            # City node + LIVES_IN edge
            city, state = rec.get("city", ""), rec.get("state", "")
            city_key = f"{city}_{state}"
            if city:
                if city_key not in seen_cities:
                    execute_query(client, graph_id, f"MERGE (ci:City {{name: '{_escape(city)}', state: '{_escape(state)}'}})")
                    seen_cities.add(city_key)
                    stats["cities_created"] += 1
                if cid:
                    execute_query(client, graph_id, f"""
                        MATCH (c:Client {{client_id: {cid}}})
                        MATCH (ci:City {{name: '{_escape(city)}', state: '{_escape(state)}'}})
                        MERGE (c)-[:LIVES_IN]->(ci)""")
                    stats["edges_created"] += 1

            # Stock nodes + HOLDS edges
            holdings = rec.get("holdings", "")
            if holdings:
                for ticker in [t.strip() for t in holdings.split(",") if t.strip()]:
                    if ticker not in seen_stocks:
                        execute_query(client, graph_id, f"MERGE (s:Stock {{ticker: '{_escape(ticker.upper())}'}})")
                        seen_stocks.add(ticker)
                        stats["stocks_created"] += 1
                    if cid:
                        execute_query(client, graph_id, f"""
                            MATCH (c:Client {{client_id: {cid}}})
                            MATCH (s:Stock {{ticker: '{_escape(ticker.upper())}'}})
                            MERGE (c)-[:HOLDS]->(s)""")
                        stats["edges_created"] += 1

            # RiskProfile node + HAS_RISK_PROFILE edge
            risk = rec.get("risk_tolerance", "")
            if risk:
                if risk not in seen_risk_profiles:
                    execute_query(client, graph_id, f"MERGE (r:RiskProfile {{level: '{_escape(risk)}'}})")
                    seen_risk_profiles.add(risk)
                    stats["risk_profiles_created"] += 1
                if cid:
                    execute_query(client, graph_id, f"""
                        MATCH (c:Client {{client_id: {cid}}})
                        MATCH (r:RiskProfile {{level: '{_escape(risk)}'}})
                        MERGE (c)-[:HAS_RISK_PROFILE]->(r)""")
                    stats["edges_created"] += 1

        except Exception as e:
            logger.warning(f"Error processing record {rec.get('client_id')}: {e}")
            stats["errors"] += 1

    return stats


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Load CSV data into Neptune Analytics graph")
    parser.add_argument("--region", default=REGION, help="AWS region")
    parser.add_argument("--csv", default=CSV_PATH, help="Path to CSV file")
    parser.add_argument("--graph-id", default=None, help="Graph ID (skip SSM lookup)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Neptune Analytics Data Loader")
    logger.info("=" * 60)

    graph_id = args.graph_id or get_graph_id(args.region)

    # Read and transform CSV
    records = read_csv(args.csv)
    if not records:
        logger.warning("No records found. Exiting.")
        sys.exit(0)

    # Load data
    stats = load_graph_data(graph_id, args.region, records)

    logger.info("\n" + "=" * 60)
    logger.info("LOAD COMPLETE - Summary:")
    logger.info("=" * 60)
    for key, val in stats.items():
        logger.info(f"  {key:25s}: {val}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
