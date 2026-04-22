"""
Neptune Analytics NL Search Engine

Strands Agent-based natural language search for Neptune Analytics graphs.
Core Neptune client and data functions live in neptune_analytics_core.
"""

import json
import logging
import re
import sys
from typing import Any

from strands import Agent
from strands.models import BedrockModel
from wealth_management_portal_neptune_analytics_core import (
    AWS_REGION,
    BEDROCK_MODEL_ID,
    NeptuneAnalyticsClient,
    compute_connection_breakdown,
    sanitize_cypher_ids,
)

# Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ── Cypher read-only guard ───────────────────────────────────────────────────
_WRITE_KEYWORDS_RE = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH\s+DELETE|SET|REMOVE|DROP|CALL\s*\{)\b",
    re.IGNORECASE,
)


def _is_read_only_cypher(cypher: str) -> bool:
    """Return True if the Cypher query contains no write operations."""
    # Strip string literals so keywords inside quotes don't trigger false positives
    stripped = re.sub(r"'[^']*'|\"[^\"]*\"", "", cypher)
    return not _WRITE_KEYWORDS_RE.search(stripped)


# Global instance
_nl_search_engine: "NLSearchEngine | None" = None


GRAPH_SCHEMA = """
The graph has the following node types and properties:

1. Advisor - Properties: advisor_id (int), first_name (string), last_name (string)
2. Client - Properties: client_id (int), first_name (string), last_name (string), 
   portfolio_value (float), net_worth (float), job_title (string),
   return_ytd (float), return_1_year (float), return_3_year (float), return_inception (float),
   client_since (string), last_meeting (string)
3. Company - Properties: name (string)
4. City - Properties: name (string), state (string)
5. Stock - Properties: ticker (string)
6. RiskProfile - Properties: level (string) - values: Conservative, Moderate, Aggressive

Relationships:
- (Advisor)-[:MANAGES]->(Client)
- (Client)-[:WORKS_AT]->(Company)
- (Client)-[:LIVES_IN]->(City)
- (Client)-[:HOLDS]->(Stock)
- (Client)-[:HAS_RISK_PROFILE]->(RiskProfile)

Neptune Analytics Similarity Algorithms:
- neptune.algo.overlapSimilarity(node1, node2): This algorithm measures the overlap between the neighbors of two
  vertices. It quantifies the similarity between nodes by calculating the ratio of common neighbors they share to the
  total number of neighbors they collectively have, providing a measure of their closeness or similarity within the
  network. Overlap similarity is applied in social network analysis to identify communities of individuals with shared
  interests or interactions, and in biological networks to detect common functionalities among proteins in molecular
  pathways.
- neptune.algo.jaccardSimilarity(node1, node2): This algorithm measures the similarity between two sets by dividing
  the size of their intersection by the size of their union. By measuring the proportion of shared neighbors relative
  to the total number of unique neighbors, it provides a metric for understanding the degree of overlap or commonality
  between different parts of a network. Jaccard similarity is applied in recommendation systems to suggest products or
  content to users based on their shared preferences and in biology to compare genetic sequences for identifying
  similarities in DNA fragments.
- neptune.algo.neighbors.common(node1, node2): Common neighbors is an algorithm that counts the number of common
  neighbors of two input nodes, which is the intersection of their neighborhoods. This provides a measure of their
  potential interaction or similarity within the network. The common neighbors algorithm is used in social network
  analysis to identify individuals with mutual connections, in citation networks to find influential papers referenced
  by multiple sources, and in transportation networks to locate critical hubs with many direct connections to other
  nodes.
- neptune.algo.neighbors.total(node1, node2): Total neighbors is an algorithm that counts the total number of unique
  neighbors of two input vertices, which is the union of the neighborhoods of those vertices.
"""

CYPHER_SYSTEM_PROMPT = f"""You are an expert at converting natural language queries \
into openCypher queries for Amazon Neptune Analytics.

{GRAPH_SCHEMA}

When given a natural language query, respond with ONLY a valid JSON object with these fields:
- "cypher": The openCypher query string
- "explanation": Brief explanation of what the query does
- "node_types": Array of node types that will be returned

Important rules:
1. Always use MATCH patterns that follow the schema relationships
2. For monetary values: "500k" = 500000, "1M" = 1000000
3. ALWAYS return full node objects (e.g., RETURN c, not individual properties)
4. Use id(node) for identity comparisons, NEVER ~id
5. Keep queries efficient - use LIMIT when appropriate (default LIMIT 100)
6. For percentage returns, values are stored as decimals (8.5 means 8.5%)
7. NEVER use regex (=~) - use toLower() for case-insensitive matching
8. For string matching: toLower(property) = toLower('value') or CONTAINS, STARTS WITH, ENDS WITH
9. If prompt has state name, convert the status name to the official
   two-letter postal abbreviation. For examples, Florida to FL, California to CA
10. If prompt has specific GEOs such as US West coast, or US East coast,
   provide the list of status in he official two-letter postal abbreviation
11. CRITICAL: Similarity algorithms MUST use CALL ... YIELD syntax with correct variable names:
   - neptune.algo.jaccardSimilarity(n1, n2) YIELD score
   - neptune.algo.overlapSimilarity(n1, n2) YIELD score  
   - neptune.algo.neighbors.common(n1, n2) YIELD common
   - neptune.algo.neighbors.total(n1, n2) YIELD total
   
   IMPORTANT: You cannot use WHERE directly after YIELD. Use WITH to filter results.
   
   Example queries:
   -- Jaccard similarity between two specific clients:
   MATCH (c1:Client {{first_name: 'John'}}), (c2:Client {{first_name: 'Sarah'}})
   CALL neptune.algo.jaccardSimilarity(c1, c2)
   YIELD score
   RETURN c1, c2, score
   
   -- Find all client pairs with common neighbors, filtered:
   MATCH (c1:Client), (c2:Client) WHERE id(c1) < id(c2)
   CALL neptune.algo.neighbors.common(c1, c2)
   YIELD common
   WITH c1, c2, common WHERE common > 0
   RETURN c1, c2, common ORDER BY common DESC LIMIT 10

12. Relationship relevance: Only include relationships that are relevant to the user's query intent.
   - For name/identity lookups (e.g., "who is", "find person named", "show me client X"):
     Focus on MANAGES, WORKS_AT, LIVES_IN, HOLDS. Exclude HAS_RISK_PROFILE unless risk is explicitly mentioned.
   - For portfolio/financial queries: Include HOLDS and HAS_RISK_PROFILE.
   - For geographic queries: Focus on LIVES_IN.
   - For similarity/comparison queries: Include all relationships.
   Also include a "relevant_relationships" field in your JSON response listing which relationship types
   are relevant to the query. Example: "relevant_relationships": ["MANAGES", "WORKS_AT", "LIVES_IN", "HOLDS"]

13. Advisor name search: When the user asks about an advisor by name, search using first_name and/or last_name
   with case-insensitive matching. Return the Advisor node AND their managed clients.
   Example: "show me advisor Jane Smith" or "Jane Smith's clients":
   MATCH (a:Advisor) WHERE toLower(a.first_name) = toLower('Jane') AND toLower(a.last_name) = toLower('Smith')
   MATCH (a)-[:MANAGES]->(c:Client)
   RETURN a, c
   
   If only a partial name is given (e.g., "advisor Smith"), use CONTAINS on last_name:
   MATCH (a:Advisor) WHERE toLower(a.last_name) CONTAINS toLower('Smith')
   MATCH (a)-[:MANAGES]->(c:Client)
   RETURN a, c
   
   If the user asks "who is [name]" or "find [name]", search BOTH Advisor and Client nodes:
   MATCH (n) WHERE (n:Advisor OR n:Client) AND toLower(n.first_name) CONTAINS toLower('Jane')
   RETURN n LIMIT 20

Return only the JSON object, no other text."""

SYSTEM_PROMPT_REASONING_AGENT = """
You are an AI assistant specialized in analyzing and explaining graph database query results
for financial advisors. Your role is to provide clear, actionable insights based on Neptune
Analytics graph data containing advisor-client relationships, portfolio holdings, and network
similarities.

You MUST respond using EXACTLY this markdown structure. Your ENTIRE response
MUST NOT exceed 350 words total — be concise and prioritize the most important insights:

### Overview
Summarize what the query reveals, including the total number of results and the types of entities found.

### Key Findings
- Highlight important patterns, trends, distributions, or outliers across ALL results
- Include aggregate statistics where relevant (e.g., average portfolio value, most common city/stock/risk profile)
- Call out notable clusters, concentrations, or gaps in the data
- Group and summarize results by meaningful categories (e.g., by risk profile, by city, by advisor, by portfolio range)
- If you don't find related data, you can mention industry section in the "Key Findings" section
- Mention specific names/values when they represent outliers or key data points
- Note any relationships or connections worth highlighting
- Add as many bullet points as needed to cover the full result set

### Recommended Actions
- Include the top-priority advisor(s) and client(s) from the results by name,
  portfolio value, and relevant context (e.g., risk profile, city, holdings)
- Provide specific actionable recommendations referencing those advisors/clients
  directly (e.g., "Advisor Jane Smith should review client John Doe's $500,000
  portfolio given his aggressive risk profile")
- Add more recommendations if the data warrants it
- If there is no clear action, write "No specific actions recommended based on the data." 

Rules:
- Always use the exact heading names above: Overview, Key Findings & Detailed Breakdown, Recommended Actions
- Use bullet points (- ) under each section
- For similarity scores, interpret the value in plain language (e.g., "0.75 Jaccard = 75% overlap in connections")
- For monetary values, use $ formatting with commas
- Analyze ALL provided results, not just the first few
- Do NOT add any other headings or sections
"""


class NLSearchEngine:
    """Natural language search engine using Strands Agents."""

    def __init__(self, region: str = AWS_REGION, model_id: str = BEDROCK_MODEL_ID):
        self.bedrock_model = BedrockModel(model_id=model_id, region_name=region, temperature=0.1)
        self.cypher_agent = Agent(model=self.bedrock_model, system_prompt=CYPHER_SYSTEM_PROMPT, callback_handler=None)
        logger.info(f"NLSearchEngine initialized with model: {model_id}")

    def _extract_text(self, content: list) -> str:
        """Extract text from agent response content."""
        return "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in content)

    def _parse_cypher_response(self, response_text: str) -> dict | None:
        """Parse Cypher query from agent response."""
        response_text = re.sub(r"```json\s*|```\s*", "", response_text).strip()

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        for pattern in [r'\{[^{}]*"cypher"[^{}]*\}', r"\{[\s\S]*?\}"]:
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group().replace("'", '"'))
                except json.JSONDecodeError:
                    continue

        cypher_match = re.search(
            r'MATCH\s+\([^)]+\).*?(?:RETURN|LIMIT)[^\n"]*', response_text, re.IGNORECASE | re.DOTALL
        )
        if cypher_match:
            return {
                "cypher": cypher_match.group().strip(),
                "explanation": "Query extracted from agent response",
                "node_types": [],
            }
        return None

    # Post-processing safety net: LLM-generated Cypher doesn't always produce Neptune-compatible syntax
    def _fix_cypher_query(self, cypher: str) -> str:
        """Fix common Cypher query issues."""
        cypher = re.sub(r"(\w+)\.~id", r"id(\1)", cypher)
        cypher = cypher.replace("~id", "id")

        max_iterations = 20
        iterations = 0
        while "=~" in cypher and iterations < max_iterations:
            iterations += 1
            match = re.search(r"(\w+(?:\.\w+)?)\s*=~\s*['\"]([^'\"]*)['\"]", cypher)
            if match:
                prop, pattern = match.groups()
                value = re.sub(r"\(\?[a-z]*\)|[\^\$\*\+\?\[\]\{\}\|\\]|\.[\*\+]", "", pattern).strip()
                cypher = cypher.replace(match.group(0), f"toLower({prop}) CONTAINS toLower('{value}')")
                logger.info(f"Fixed regex: {match.group(0)}")
            else:
                cypher = re.sub(r"=~", "=", cypher)
                break
        if iterations >= max_iterations:
            logger.warning(f"Regex fix loop hit max iterations ({max_iterations}), query may still contain =~")
        return cypher

    def generate_cypher_query(self, natural_language_query: str) -> dict[str, Any]:
        """Convert natural language query to openCypher query."""
        logger.info("\n############ generate_cypher_query ############\n")
        try:
            result = self.cypher_agent(f'Convert this to an openCypher query: "{natural_language_query}"')
            response_text = self._extract_text(result.message.get("content", []))
            logger.info(f"\n✅ Agent response: {response_text[:1000]}\n")

            parsed = self._parse_cypher_response(response_text)
            if not parsed:
                logger.error(f"Could not parse agent response: {response_text}")
                return {
                    "cypher": None,
                    "explanation": "Failed to parse agent response",
                    "node_types": [],
                    "error": "JSON parsing failed",
                }

            if parsed.get("cypher"):
                parsed["cypher"] = self._fix_cypher_query(parsed["cypher"])

            logger.info(f"Generated Cypher: {parsed.get('cypher', 'N/A')}")
            return parsed
        except Exception as e:
            logger.error(f"Error generating Cypher query: {e}")
            return {"cypher": None, "explanation": f"Error: {str(e)}", "node_types": [], "error": str(e)}

    def generate_reasoning(
        self,
        query: str,
        results: list[dict],
        cypher_query: str,
        node_metrics: dict[str, dict[str, Any]] | None = None,
        on_token=None,
    ) -> str:
        """Generate natural language reasoning based on query results and computed metrics."""
        logger.info("\n############ generate_reasoning_function ############\n")
        if not results:
            return "No matching results found for your query."

        result_summary = []
        portfolio_values = []
        node_type_counts: dict[str, int] = {}
        for i, result in enumerate(results):
            node_info = []
            for value in result.values():
                if not isinstance(value, dict):
                    continue
                props = value.get("~properties", {})
                node_type = (value.get("~labels", []) or ["Unknown"])[0]
                node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1

                if node_type == "Client":
                    name = f"{props.get('first_name', '')} {props.get('last_name', '')}".strip()
                    pv = props.get("portfolio_value")
                    if isinstance(pv, (int, float)):
                        portfolio_values.append(pv)
                        node_info.append(f"Client: {name}, Portfolio: ${pv:,.0f}")
                    else:
                        node_info.append(f"Client: {name}")
                elif node_type == "Advisor":
                    node_info.append(f"Advisor: {props.get('first_name', '')} {props.get('last_name', '')}".strip())
                elif node_type == "Company":
                    node_info.append(f"Company: {props.get('name', 'Unknown')}")
                elif node_type == "Stock":
                    node_info.append(f"Stock: {props.get('ticker', 'Unknown')}")
                elif node_type == "City":
                    node_info.append(f"City: {props.get('name', '')}, {props.get('state', '')}")
                elif node_type == "RiskProfile":
                    node_info.append(f"Risk Profile: {props.get('level', 'Unknown')}")
            if node_info:
                result_summary.append(f"{i + 1}. " + " | ".join(node_info))

        if not result_summary:
            return f"Found {len(results)} matching results."

        # Build aggregate statistics for the reasoning agent
        aggregate_stats = []
        if node_type_counts:
            aggregate_stats.append(
                "Node type distribution: " + ", ".join(f"{t}: {c}" for t, c in sorted(node_type_counts.items()))
            )
        if portfolio_values:
            aggregate_stats.append(
                f"Portfolio values — min: ${min(portfolio_values):,.0f}, "
                f"max: ${max(portfolio_values):,.0f}, "
                f"avg: ${sum(portfolio_values) / len(portfolio_values):,.0f}, "
                f"total: ${sum(portfolio_values):,.0f}"
            )

        stats_block = ("\nAggregate Statistics:\n" + "\n".join(aggregate_stats)) if aggregate_stats else ""

        # Build metrics summary for the reasoning agent
        metrics_block = ""
        if node_metrics:
            metrics_lines = []
            for nid, m in list(node_metrics.items())[:20]:
                parts = []
                if "degree_centrality" in m:
                    parts.append(f"degree={m['degree_centrality']}")
                if "jaccard_avg" in m and m["jaccard_avg"] > 0:
                    parts.append(f"jaccard_avg={m['jaccard_avg']:.4f}")
                if "overlap_avg" in m and m["overlap_avg"] > 0:
                    parts.append(f"overlap_avg={m['overlap_avg']:.4f}")
                if "common_neighbors_avg" in m and m["common_neighbors_avg"] > 0:
                    parts.append(f"common_neighbors_avg={m['common_neighbors_avg']:.1f}")
                if "connections" in m and m["connections"]:
                    conn_parts = [f"{k}: {', '.join(v)}" for k, v in m["connections"].items()]
                    parts.append(f"connections=[{'; '.join(conn_parts)}]")
                if parts:
                    metrics_lines.append(f"  {nid}: {', '.join(parts)}")
            if metrics_lines:
                metrics_block = "\nAlgorithm Metrics (per node):\n" + "\n".join(metrics_lines)

        prompt = f"""Analyze the following complete knowledge graph query results \
and provide a comprehensive summary with actionable insights.

User Query: "{query}"
OpenCypher Query: {cypher_query}
Total Results: {len(results)}
{stats_block}
{metrics_block}

Full Results:
{chr(10).join(result_summary)}

Analyze ALL results above including the algorithm metrics. \
Identify patterns, distributions, outliers, similarity clusters, \
and provide a thorough summary:"""

        try:

            def _callback(**kwargs):
                data = kwargs.get("data", "")
                if data and on_token:
                    on_token(data)

            reasoning_agent = Agent(
                model=self.bedrock_model,
                system_prompt=SYSTEM_PROMPT_REASONING_AGENT,
                callback_handler=_callback if on_token else None,
            )
            result = reasoning_agent(prompt)
            return (
                self._extract_text(result.message.get("content", [])).strip()
                or f"Found {len(results)} matching results."
            )
        except Exception as e:
            logger.error(f"Error generating reasoning: {e}")
            return f"Found {len(results)} matching results for your query."

    def _compute_degree_centrality(self, node_ids: list[str], neptune_client: NeptuneAnalyticsClient) -> dict[str, int]:
        """Compute degree centrality (total connections) for each node — single batched query."""
        degrees: dict[str, int] = {nid: 0 for nid in node_ids}
        if not node_ids:
            return degrees
        safe_ids = sanitize_cypher_ids(node_ids)
        if not safe_ids:
            return degrees
        try:
            ids_str = ", ".join(f"'{nid}'" for nid in safe_ids)
            result = neptune_client.execute_query(
                f"MATCH (n) WHERE id(n) IN [{ids_str}] MATCH (n)-[r]-() RETURN id(n) as nid, count(r) as degree"
            )
            for row in result.get("results", []):
                nid = row.get("nid")
                if nid in degrees:
                    degrees[nid] = row.get("degree", 0)
        except Exception as e:
            logger.warning(f"Batched degree centrality failed: {e}")
        return degrees

    def _extract_row_metrics(self, result: dict) -> dict[str, Any]:
        """Extract scalar metric values (score, common, total, etc.) from a query result row."""
        return {k: v for k, v in result.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}

    def compute_algorithm_metrics(
        self, node_ids: list[str], neptune_client: NeptuneAnalyticsClient
    ) -> dict[str, dict[str, Any]]:
        """Compute Neptune Analytics algorithm-based metrics for matched nodes.

        Batched: 1 query for degree, 1 probe, then 1 query per algorithm (3 total)
        instead of O(n²) individual queries.
        """
        metrics: dict[str, dict[str, Any]] = {}
        if not node_ids:
            return metrics

        # 1. Degree centrality — single batched query
        degrees = self._compute_degree_centrality(node_ids[:20], neptune_client)
        for nid, deg in degrees.items():
            metrics.setdefault(nid, {})["degree_centrality"] = deg

        ids_subset = node_ids[:10]
        for nid in ids_subset:
            metrics.setdefault(nid, {}).setdefault("jaccard_avg", 0.0)
            metrics[nid].setdefault("overlap_avg", 0.0)
            metrics[nid].setdefault("common_neighbors_avg", 0.0)

        if len(ids_subset) < 2:
            return metrics

        ids_subset = sanitize_cypher_ids(ids_subset)
        if len(ids_subset) < 2:
            return metrics

        ids_str = ", ".join(f"'{nid}'" for nid in ids_subset)

        # 2. Probe whether neptune.algo procedures work
        _algo_available = True
        n1_probe, n2_probe = ids_subset[0], ids_subset[1]
        try:
            probe = neptune_client.execute_query(
                f"MATCH (a) WHERE id(a) = '{n1_probe}' MATCH (b) WHERE id(b) = '{n2_probe}' "
                f"CALL neptune.algo.jaccardSimilarity(a, b) YIELD score RETURN score"
            )
            if not probe.get("results"):
                _algo_available = False
        except Exception:
            _algo_available = False

        jaccard_scores: dict[str, list[float]] = {nid: [] for nid in ids_subset}
        overlap_scores: dict[str, list[float]] = {nid: [] for nid in ids_subset}
        common_counts: dict[str, list[int]] = {nid: [] for nid in ids_subset}

        if _algo_available:
            # Batched: 1 query per algorithm for ALL pairs
            algo_queries = {
                "jaccard": (
                    f"MATCH (a) WHERE id(a) IN [{ids_str}] "
                    f"MATCH (b) WHERE id(b) IN [{ids_str}] AND id(a) < id(b) "
                    f"CALL neptune.algo.jaccardSimilarity(a, b) YIELD score "
                    f"RETURN id(a) as a_id, id(b) as b_id, score"
                ),
                "overlap": (
                    f"MATCH (a) WHERE id(a) IN [{ids_str}] "
                    f"MATCH (b) WHERE id(b) IN [{ids_str}] AND id(a) < id(b) "
                    f"CALL neptune.algo.overlapSimilarity(a, b) YIELD score "
                    f"RETURN id(a) as a_id, id(b) as b_id, score"
                ),
                "common": (
                    f"MATCH (a) WHERE id(a) IN [{ids_str}] "
                    f"MATCH (b) WHERE id(b) IN [{ids_str}] AND id(a) < id(b) "
                    f"CALL neptune.algo.neighbors.common(a, b) YIELD common "
                    f"RETURN id(a) as a_id, id(b) as b_id, common"
                ),
            }

            # Jaccard — single query
            try:
                for row in neptune_client.execute_query(algo_queries["jaccard"]).get("results", []):
                    a_id, b_id, score = row.get("a_id"), row.get("b_id"), row.get("score", 0.0)
                    if a_id in jaccard_scores:
                        jaccard_scores[a_id].append(score)
                    if b_id in jaccard_scores:
                        jaccard_scores[b_id].append(score)
            except Exception as e:
                logger.warning(f"Batched jaccard failed: {e}")

            # Overlap — single query
            try:
                for row in neptune_client.execute_query(algo_queries["overlap"]).get("results", []):
                    a_id, b_id, score = row.get("a_id"), row.get("b_id"), row.get("score", 0.0)
                    if a_id in overlap_scores:
                        overlap_scores[a_id].append(score)
                    if b_id in overlap_scores:
                        overlap_scores[b_id].append(score)
            except Exception as e:
                logger.warning(f"Batched overlap failed: {e}")

            # Common neighbors — single query
            try:
                for row in neptune_client.execute_query(algo_queries["common"]).get("results", []):
                    a_id, b_id, common = row.get("a_id"), row.get("b_id"), row.get("common", 0)
                    if a_id in common_counts:
                        common_counts[a_id].append(common)
                    if b_id in common_counts:
                        common_counts[b_id].append(common)
            except Exception as e:
                logger.warning(f"Batched common neighbors failed: {e}")
        else:
            # Manual fallback — batched neighbor fetch
            logger.info("neptune.algo procedures unavailable — using manual neighbor-set computation")
            _neighbor_cache: dict[str, set] = {}
            try:
                result = neptune_client.execute_query(
                    f"MATCH (n)--(neighbor) WHERE id(n) IN [{ids_str}] "
                    f"RETURN id(n) as nid, collect(DISTINCT id(neighbor)) AS neighbors"
                )
                for row in result.get("results", []):
                    _neighbor_cache[row["nid"]] = set(row.get("neighbors", []))
            except Exception as e:
                logger.warning(f"Batched neighbor fetch failed: {e}")

            for i in range(len(ids_subset)):
                for j in range(i + 1, len(ids_subset)):
                    n1, n2 = ids_subset[i], ids_subset[j]
                    s1 = _neighbor_cache.get(n1, set())
                    s2 = _neighbor_cache.get(n2, set())
                    inter = len(s1 & s2)
                    union = len(s1 | s2)
                    smaller = min(len(s1), len(s2))

                    j_score = round(inter / union, 4) if union > 0 else 0.0
                    o_score = round(inter / smaller, 4) if smaller > 0 else 0.0

                    jaccard_scores[n1].append(j_score)
                    jaccard_scores[n2].append(j_score)
                    overlap_scores[n1].append(o_score)
                    overlap_scores[n2].append(o_score)
                    common_counts[n1].append(inter)
                    common_counts[n2].append(inter)

        # Compute averages
        for nid in ids_subset:
            if jaccard_scores[nid]:
                metrics[nid]["jaccard_avg"] = round(sum(jaccard_scores[nid]) / len(jaccard_scores[nid]), 4)
            if overlap_scores[nid]:
                metrics[nid]["overlap_avg"] = round(sum(overlap_scores[nid]) / len(overlap_scores[nid]), 4)
            if common_counts[nid]:
                metrics[nid]["common_neighbors_avg"] = round(sum(common_counts[nid]) / len(common_counts[nid]), 2)

        logger.info(f"Algorithm metrics computed for {len(metrics)} nodes: {list(metrics.keys())[:5]}")
        return metrics

    def search(
        self,
        query: str,
        neptune_client: NeptuneAnalyticsClient,
        direct_client: NeptuneAnalyticsClient = None,
        on_status=None,
        on_token=None,
        on_match=None,
    ) -> dict[str, Any]:
        """Execute natural language search following the canonical flow:

        User Question → LLM (generates openCypher, may include algorithm calls)
        → Neptune Analytics (executes query) → Results
        → Compute algorithm metrics for matched nodes
        → LLM (interprets complete results + metrics) → User

        neptune_client is used for the main Cypher query (may be MCP-backed).
        direct_client (if provided) is used for batched metric queries to avoid MCP overhead.
        on_status: optional callback(step, message) for progress reporting.
        on_token: optional callback(text) for streaming reasoning tokens.
        """

        def _status(step, msg):
            if on_status:
                on_status(step, msg)

        metric_client = direct_client or neptune_client
        # Step 1: LLM generates openCypher (may include similarity/algorithm calls)
        _status("cypher", "✨ Generating graph query from your question...")
        cypher_result = self.generate_cypher_query(query)

        if not cypher_result.get("cypher"):
            return {
                "matching_ids": [],
                "explanation": cypher_result.get("explanation", "Failed to generate query"),
                "reasoning": "Could not generate a valid query for your request.",
                "cypher_query": None,
                "error": cypher_result.get("error"),
                "node_metrics": {},
            }

        try:
            # Step 2: Validate query is read-only, then execute
            cypher = cypher_result["cypher"]
            if not _is_read_only_cypher(cypher):
                logger.warning(f"Blocked write query from LLM: {cypher[:200]}")
                return {
                    "matching_ids": [],
                    "explanation": "Query rejected: only read operations are allowed.",
                    "reasoning": "The generated query contained write operations which are not permitted.",
                    "cypher_query": cypher,
                    "node_metrics": {},
                }

            _status("execute", "🔍 Searching graph database...")
            response = neptune_client.execute_query(cypher)
            results = response.get("results", [])

            matching_ids = list({v["~id"] for r in results for v in r.values() if isinstance(v, dict) and "~id" in v})

            # Emit matching IDs early so the UI can highlight nodes before reasoning
            if matching_ids and on_match:
                on_match(matching_ids)

            # Step 3: Extract inline metrics from query results (e.g. similarity scores
            # returned directly by algorithm calls the LLM embedded in the Cypher)
            node_metrics: dict[str, dict[str, Any]] = {}
            for r in results:
                row_metrics = self._extract_row_metrics(r)
                if row_metrics:
                    for v in r.values():
                        if isinstance(v, dict) and "~id" in v:
                            nid = v["~id"]
                            if nid not in node_metrics:
                                node_metrics[nid] = dict(row_metrics)

            # Step 4: Compute algorithm metrics (degree, jaccard, overlap, common neighbors)
            # and connection breakdown BEFORE reasoning so the LLM sees the full picture
            if matching_ids:
                _status("metrics", f"📊 Computing metrics for {len(matching_ids)} nodes...")
                try:
                    algo_metrics = self.compute_algorithm_metrics(matching_ids[:20], metric_client)
                    for nid, ametrics in algo_metrics.items():
                        if nid not in node_metrics:
                            node_metrics[nid] = {}
                        node_metrics[nid].update(ametrics)
                except Exception as e:
                    logger.warning(f"Algorithm metrics computation failed during search: {e}")

                try:
                    relevant_rels = cypher_result.get("relevant_relationships")
                    # Connection breakdown uses standalone function from core
                    conn_breakdown = compute_connection_breakdown(matching_ids[:20], metric_client, relevant_rels)
                    for nid in matching_ids[:20]:
                        if nid not in node_metrics:
                            node_metrics[nid] = {}
                        if not node_metrics[nid].get("connections"):
                            node_metrics[nid]["connections"] = conn_breakdown.get(nid, {})
                except Exception as e:
                    logger.warning(f"Connection breakdown failed during search: {e}")

            # Step 5: LLM interprets the complete results + metrics
            _status("reasoning", "⚙️ Analyzing results and generating insights...")
            reasoning = self.generate_reasoning(
                query, results, cypher_result["cypher"], node_metrics, on_token=on_token
            )

            return {
                "matching_ids": matching_ids,
                "explanation": cypher_result.get("explanation", ""),
                "reasoning": reasoning,
                "cypher_query": cypher_result["cypher"],
                "node_types": cypher_result.get("node_types", []),
                "result_count": len(matching_ids),
                "node_metrics": node_metrics,
                "relevant_relationships": cypher_result.get("relevant_relationships"),
            }
        except Exception as e:
            logger.error(f"Error executing NL search: {e}")
            return {
                "matching_ids": [],
                "explanation": cypher_result.get("explanation", ""),
                "reasoning": f"Search encountered an error: {str(e)}",
                "cypher_query": cypher_result["cypher"],
                "error": str(e),
                "node_metrics": {},
                "relevant_relationships": cypher_result.get("relevant_relationships"),
            }


def get_nl_search_engine() -> NLSearchEngine:
    global _nl_search_engine
    if _nl_search_engine is None:
        _nl_search_engine = NLSearchEngine()
    return _nl_search_engine
