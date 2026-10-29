"""Evidence Gatherer tools — KB search and document retrieval."""

from __future__ import annotations

import logging
import os

import boto3
from strands import tool

logger = logging.getLogger(__name__)

_bedrock_agent_runtime = None


def _get_client():
    global _bedrock_agent_runtime
    if _bedrock_agent_runtime is None:
        _bedrock_agent_runtime = boto3.client(
            "bedrock-agent-runtime",
            region_name=os.environ.get("AWS_REGION", "us-west-2"),
        )
    return _bedrock_agent_runtime


def _build_kb_filter(portfolio_id: str, doc_type: str | None = None) -> dict:
    must = [{"equals": {"key": "portfolio_id", "value": portfolio_id}}]
    if doc_type:
        must.append({"equals": {"key": "doc_type", "value": doc_type}})
    return must[0] if len(must) == 1 else {"andAll": must}


@tool
def kb_search(query: str, portfolio_id: str, top_k: int = 5) -> list[dict]:
    """Search Bedrock Knowledge Base for fund documents matching a due diligence criterion query.

    Args:
        query: Natural language search query for the criterion.
        portfolio_id: Fund identifier to restrict search scope.
        top_k: Maximum number of results to return (default 5).

    Returns:
        List of dicts with keys: doc_id, passage, score, source_uri.
    """
    kb_id = os.environ.get("BEDROCK_KB_ID")
    if not kb_id:
        logger.warning("BEDROCK_KB_ID not set — returning empty results")
        return []

    try:
        client = _get_client()
        resp = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": top_k,
                    "filter": _build_kb_filter(portfolio_id),
                }
            },
        )
        results = []
        for item in resp.get("retrievalResults", []):
            results.append(
                {
                    "doc_id": item.get("metadata", {}).get("doc_id", ""),
                    "passage": item.get("content", {}).get("text", ""),
                    "score": item.get("score", 0.0),
                    "source_uri": item.get("location", {}).get("s3Location", {}).get("uri", ""),
                }
            )
        return results
    except Exception as exc:
        logger.error("KB search failed: %s", exc)
        return []


@tool
def get_document_excerpt(doc_id: str, passage_ids: list[str]) -> dict:
    """Retrieve specific passages from an S3 fund document.

    Args:
        doc_id: Document identifier.
        passage_ids: List of passage identifiers to retrieve.

    Returns:
        Dict with keys: doc_id, passages (list of {id, text}), retrieved_at.
    """
    # In demo mode, passages come from KB search results stored in state.
    # In production, this would fetch directly from S3.
    return {
        "doc_id": doc_id,
        "passages": [{"id": pid, "text": ""} for pid in passage_ids],
        "retrieved_at": "",
    }
