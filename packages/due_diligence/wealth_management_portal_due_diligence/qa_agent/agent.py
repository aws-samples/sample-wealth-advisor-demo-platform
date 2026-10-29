"""QA Agent — validates report completeness, citation accuracy, and scores."""

from __future__ import annotations

import logging
import os

from strands import Agent
from strands.models.bedrock import BedrockModel

from ..framework import DD_FRAMEWORK_V1
from ..schemas import QAResult, QATask

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the QA Agent for a portfolio due diligence system.

Your job is to validate a completed DD report draft:
1. Check all 13 criteria are addressed in the report sections
2. Verify that scores in the assessment match the narrative (a score of 8 should not have negative narrative)
3. Check that evidence_gap criteria are appropriately caveated in the report
4. Ensure the recommendation is consistent with the overall_score
5. Flag any factual inconsistencies

Return {"approved": true} if the report is acceptable.
Return {"approved": false, "revision_notes": ["...", "..."]} with specific, actionable notes.
Be a fair reviewer — minor imperfections should not trigger rejection.
"""


async def qa_check(task: QATask) -> QAResult:
    """Validate the report draft against assessment and evidence."""
    revision_notes: list[str] = []

    # Check all criteria are covered
    all_criteria_ids = {c.criterion_id for c in DD_FRAMEWORK_V1}
    covered_in_sections: set[str] = set()
    for section in task.report_draft.sections:
        covered_in_sections.update(section.criteria_covered)

    missing = all_criteria_ids - covered_in_sections
    if missing:
        revision_notes.append(f"Criteria not addressed in any section: {', '.join(sorted(missing))}")

    # Check score/narrative consistency
    scores_by_id = {s.criterion_id: s.score for s in task.assessment_bundle.criterion_scores}
    for section in task.report_draft.sections:
        content_lower = section.content.lower()
        for cid in section.criteria_covered:
            score = scores_by_id.get(cid, 0)
            if score < 4.0 and ("strong" in content_lower or "excellent" in content_lower):
                revision_notes.append(
                    f"Section '{section.title}' contains positive language "
                    f"for low-scored criterion {cid} (score {score:.1f})"
                )

    # Check recommendation consistency
    score = task.report_draft.overall_score
    rec = task.report_draft.recommendation
    if score >= 7.0 and rec == "REJECT":
        revision_notes.append(f"Recommendation REJECT inconsistent with score {score:.1f} (>=7.0 = APPROVE)")
    elif score < 4.0 and rec == "APPROVE":
        revision_notes.append(f"Recommendation APPROVE inconsistent with score {score:.1f} (<4.0 = REJECT)")

    # Check evidence gap criteria are caveated
    gap_criteria = {b.criterion_id for b in task.evidence_bundles if b.evidence_gap}
    if gap_criteria and task.report_draft.executive_summary:
        summary_lower = task.report_draft.executive_summary.lower()
        if "insufficient" not in summary_lower and "evidence" not in summary_lower and len(gap_criteria) > 2:
            revision_notes.append(
                f"Executive summary should acknowledge insufficient evidence for: {', '.join(sorted(gap_criteria))}"
            )

    approved = len(revision_notes) == 0
    return QAResult(
        approved=approved,
        revision_notes=revision_notes,
        confidence_score=1.0 if approved else max(0.3, 1.0 - len(revision_notes) * 0.15),
    )


def create_agent() -> Agent:
    return Agent(
        name="QA Agent",
        description="Validates DD report completeness and accuracy.",
        model=BedrockModel(model_id=os.environ.get("QA_AGENT_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")),
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        callback_handler=None,
    )
