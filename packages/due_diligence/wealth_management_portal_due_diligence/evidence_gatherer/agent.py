"""Evidence Gatherer Agent — retrieves KB evidence for one DD criterion."""

from __future__ import annotations

import logging
import os

from strands import Agent
from strands.models.bedrock import BedrockModel

from ..schemas import EvidenceBundle, EvidenceExcerpt, EvidenceTask
from .tools import get_document_excerpt, kb_search

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Evidence Gatherer for a portfolio due diligence system.

Your job for each task:
1. Use kb_search to retrieve relevant passages for the given criterion query
2. Use get_document_excerpt for any passages needing fuller context
3. Return only factual excerpts with source citations — do NOT score or interpret
4. If fewer than 2 relevant passages found, set evidence_gap=True

Return a JSON object matching the EvidenceBundle schema:
{"criterion_id": "...", "excerpts": [...], "evidence_gap": false}
"""


async def gather_evidence(task: EvidenceTask) -> EvidenceBundle:
    """Run KB search for a single criterion and return an EvidenceBundle."""
    results = kb_search(
        query=f"{task.criterion_label}: {task.prompt_hint}",
        portfolio_id=task.portfolio_id,
        top_k=5,
    )

    excerpts = [
        EvidenceExcerpt(
            doc_id=r["doc_id"],
            passage=r["passage"],
            source_uri=r["source_uri"],
            relevance_score=r.get("score", 0.0),
        )
        for r in results
        if r.get("passage")
    ]

    return EvidenceBundle(
        criterion_id=task.criterion_id,
        excerpts=excerpts,
        evidence_gap=len(excerpts) < 2,
    )


def create_agent() -> Agent:
    return Agent(
        name="Evidence Gatherer",
        description="Retrieves due diligence evidence from Bedrock Knowledge Base.",
        model=BedrockModel(
            model_id=os.environ.get("EVIDENCE_GATHERER_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
        ),
        system_prompt=SYSTEM_PROMPT,
        tools=[kb_search, get_document_excerpt],
        callback_handler=None,
    )
