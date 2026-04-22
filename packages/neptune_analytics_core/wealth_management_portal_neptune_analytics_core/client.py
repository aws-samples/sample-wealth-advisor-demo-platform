"""Neptune Analytics client and configuration constants."""

import json
import logging
import os
import re
import sys
from typing import Any

import boto3
import yaml

# ── Cypher sanitization ─────────────────────────────────────────────────────
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-:]+$")


def sanitize_cypher_ids(ids: list[str]) -> list[str]:
    """Keep only IDs matching Neptune's safe format (alphanumeric, hyphens, underscores, colons)."""
    return [i for i in ids if _SAFE_ID_RE.match(i)]


def sanitize_cypher_str(val: str) -> str:
    """Escape a value for safe interpolation inside a single-quoted Cypher string."""
    return val.replace("\\", "\\\\").replace("'", "\\'")


# Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Load unified configuration from graph_config.yaml (env vars override)
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graph_config.yaml")
_config: dict = {}
try:
    with open(_CONFIG_PATH) as _f:
        _config = yaml.safe_load(_f) or {}
    logger.info(f"Loaded configuration from {_CONFIG_PATH}")
except FileNotFoundError:
    logger.warning(f"graph_config.yaml not found at {_CONFIG_PATH}, using env vars / defaults")

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
NEPTUNE_GRAPH_ID = os.environ.get("NEPTUNE_GRAPH_ID", "")
BEDROCK_MODEL_ID = os.environ.get(
    "GRAPH_BEDROCK_MODEL_ID",
    os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
)
DEFAULT_NODE_LIMIT = int(os.environ.get("DEFAULT_NODE_LIMIT", _config.get("graph", {}).get("default_node_limit", 5000)))
MAX_NODE_LIMIT = int(os.environ.get("MAX_NODE_LIMIT", _config.get("graph", {}).get("max_node_limit", 50000)))

GRAPH_CONFIG = _config

# Global instance
_neptune_client: "NeptuneAnalyticsClient | None" = None


class NeptuneAnalyticsClient:
    """Client for Amazon Neptune Analytics using openCypher queries."""

    def __init__(self, graph_id: str = NEPTUNE_GRAPH_ID, region: str = AWS_REGION, profile_name: str = None):
        if not graph_id:
            raise ValueError("NEPTUNE_GRAPH_ID environment variable is required")
        self.graph_id = graph_id
        self.region = region
        profile = profile_name or os.environ.get("AWS_PROFILE")
        session = (
            boto3.Session(profile_name=profile, region_name=region) if profile else boto3.Session(region_name=region)
        )
        self.client = session.client("neptune-graph")
        logger.info(f"NeptuneAnalyticsClient initialized: graph_id={graph_id}, region={region}, profile={profile}")

    def execute_query(self, query: str) -> dict[str, Any]:
        """Execute an openCypher query and return results."""
        try:
            response = self.client.execute_query(
                graphIdentifier=self.graph_id, queryString=query, language="OPEN_CYPHER"
            )
            payload = response.get("payload")
            return json.loads(payload.read().decode("utf-8")) if payload else {"results": []}
        except Exception as e:
            logger.warning(f"Query execution failed: {e}")
            raise

    def test_connection(self) -> bool:
        """Test Neptune connection with a simple query."""
        try:
            self.execute_query("RETURN 1 as test")
            logger.info("Neptune connection successful!")
            return True
        except Exception as e:
            logger.error(f"Neptune connection test failed: {e}")
            return False


def get_neptune_client() -> NeptuneAnalyticsClient:
    """Return the direct boto3 Neptune client (for initial data loading, health checks)."""
    global _neptune_client
    if _neptune_client is None:
        _neptune_client = NeptuneAnalyticsClient()
    return _neptune_client
