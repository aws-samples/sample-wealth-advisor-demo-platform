"""DD Supervisor Agent — orchestrates the full due diligence pipeline."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

from strands import Agent
from strands.models.bedrock import BedrockModel

from ..common.a2a_client import get_agent_endpoint, invoke_agent
from ..framework import DD_FRAMEWORK_V1, compute_overall_recommendation, is_hitl_required, score_to_rag
from ..models import CategorySummary, CriterionAssessment, DDCategory, DDReport
from ..schemas import (
    AssessmentBundle,
    AssessmentTask,
    DDRequest,
    DraftTask,
    EvidenceBundle,
    EvidenceTask,
    QATask,
    QuantTask,
)
from ..state import AgentState, CriterionState, CriterionStatus

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the DD Supervisor for a portfolio due diligence platform.

Your role is to coordinate the full ODD/IDD pipeline:
1. Fan out to 13 Evidence Gatherer agents in parallel (one per criterion)
2. Run the Quantitative Analyst concurrently
3. Delegate all 13 criteria to the Framework Assessor with evidence + quant data
4. Send the assessment bundle to the Report Drafter
5. Run the QA Agent — if revision needed, iterate once only

Rules:
- Never assess criteria yourself; always delegate to specialists
- Use gather_all_evidence and run_quant_analysis tools concurrently
- Aggregate results into a DDReport and return it
- If any agent fails, flag that criterion as INSUFFICIENT_EVIDENCE and continue
"""


def _build_initial_state(request: DDRequest) -> AgentState:
    state = AgentState(
        session_id=request.session_id,
        portfolio_id=request.portfolio_id,
        portfolio_name=request.portfolio_name,
        manager_name=request.manager_name,
    )
    criteria_to_run = request.criteria_ids or [c.criterion_id for c in DD_FRAMEWORK_V1]
    for criterion in DD_FRAMEWORK_V1:
        if criterion.criterion_id in criteria_to_run:
            state.criteria[criterion.criterion_id] = CriterionState(
                criterion_id=criterion.criterion_id,
                category=criterion.category.value,
                weight=criterion.weight,
            )
    return state


async def _gather_evidence(state: AgentState) -> list[EvidenceBundle]:
    """Fan-out: dispatch EvidenceTasks to Evidence Gatherer agents concurrently."""
    ep = get_agent_endpoint("evidence-gatherer")

    async def gather_one(criterion_id: str) -> EvidenceBundle:
        criterion = next(c for c in DD_FRAMEWORK_V1 if c.criterion_id == criterion_id)
        task = EvidenceTask(
            session_id=state.session_id,
            portfolio_id=state.portfolio_id,
            criterion_id=criterion_id,
            criterion_label=criterion.name,
            prompt_hint=criterion.prompt_hint,
        )
        try:
            result = await invoke_agent(ep, task.model_dump_json())
            return EvidenceBundle.model_validate(result)
        except Exception as exc:
            logger.warning("Evidence gathering failed for %s: %s", criterion_id, exc)
            state.criteria[criterion_id].status = CriterionStatus.FAILED
            state.criteria[criterion_id].flags.append(str(exc))
            return EvidenceBundle(criterion_id=criterion_id, evidence_gap=True)

    bundles = await asyncio.gather(*[gather_one(cid) for cid in state.criteria])
    return list(bundles)


async def _run_quant(state: AgentState) -> dict:
    ep = get_agent_endpoint("quant-analyst")
    task = QuantTask(session_id=state.session_id, portfolio_id=state.portfolio_id)
    try:
        return await invoke_agent(ep, task.model_dump_json())
    except Exception as exc:
        logger.warning("Quant analysis failed: %s", exc)
        return {"portfolio_id": state.portfolio_id, "data_available": False}


async def _assess(state: AgentState, evidence_bundles: list[EvidenceBundle], quant_bundle: dict) -> AssessmentBundle:
    from ..schemas import QuantBundle

    ep = get_agent_endpoint("framework-assessor")
    task = AssessmentTask(
        session_id=state.session_id,
        portfolio_id=state.portfolio_id,
        evidence_bundles=evidence_bundles,
        quant_bundle=QuantBundle.model_validate(quant_bundle),
    )
    result = await invoke_agent(ep, task.model_dump_json())
    return AssessmentBundle.model_validate(result)


async def _draft_report(
    state: AgentState, bundle: AssessmentBundle, quant_bundle: dict, revision_notes: list[str]
) -> dict:
    from ..schemas import QuantBundle

    ep = get_agent_endpoint("report-drafter")
    task = DraftTask(
        session_id=state.session_id,
        portfolio_id=state.portfolio_id,
        portfolio_name=state.portfolio_name,
        manager_name=state.manager_name,
        assessment_bundle=bundle,
        quant_bundle=QuantBundle.model_validate(quant_bundle),
        revision_notes=revision_notes,
    )
    return await invoke_agent(ep, task.model_dump_json())


async def _qa_check(state: AgentState, draft: dict, evidence: list[EvidenceBundle], bundle: AssessmentBundle) -> dict:
    from ..schemas import ReportDraft

    ep = get_agent_endpoint("qa-agent")
    task = QATask(
        session_id=state.session_id,
        report_draft=ReportDraft.model_validate(draft),
        evidence_bundles=evidence,
        assessment_bundle=bundle,
    )
    return await invoke_agent(ep, task.model_dump_json())


def _build_report(state: AgentState, bundle: AssessmentBundle, draft: dict) -> DDReport:
    """Assemble the final DDReport from assessment scores and draft narrative."""
    scores_by_id = {s.criterion_id: s for s in bundle.criterion_scores}
    assessments: list[CriterionAssessment] = []

    for criterion in DD_FRAMEWORK_V1:
        cid = criterion.criterion_id
        if cid not in state.criteria:
            continue
        cs = scores_by_id.get(cid)
        score = cs.score if cs else None
        rag = score_to_rag(score)
        assessments.append(
            CriterionAssessment(
                session_id=state.session_id,
                criterion_id=cid,
                criterion_name=criterion.name,
                category=criterion.category.value,
                weight=criterion.weight,
                confidence=cs.confidence if cs else 0.0,
                score=score,
                rag_status=rag,
                summary=cs.rationale if cs else "Not assessed",
                rationale=cs.rationale if cs else "",
                hitl_required=cs.hitl_required if cs else False,
                agent_model_id=os.environ.get("DD_SUPERVISOR_MODEL_ID", ""),
                generated_at=datetime.utcnow(),
            )
        )

    recommendation, veto_reasons = compute_overall_recommendation(assessments, bundle.overall_score)
    hitl_required, hitl_reasons = is_hitl_required(assessments, recommendation)

    # Category summaries
    cat_totals: dict[DDCategory, list[tuple[float, float]]] = {cat: [] for cat in DDCategory}
    for a in assessments:
        criterion = next((c for c in DD_FRAMEWORK_V1 if c.criterion_id == a.criterion_id), None)
        if criterion and a.score is not None:
            cat_totals[criterion.category].append((a.score, criterion.weight))

    category_summaries = []
    for cat in DDCategory:
        pairs = cat_totals[cat]
        if not pairs:
            continue
        total_w = sum(w for _, w in pairs)
        cat_score = sum(s * w for s, w in pairs) / total_w if total_w else 0
        category_summaries.append(
            CategorySummary(
                category=cat,
                weight=total_w,
                weighted_score=round(cat_score * total_w, 3),
                rag_status=score_to_rag(cat_score),
            )
        )

    narrative = draft.get("executive_summary", "") if draft else ""

    return DDReport(
        session_id=state.session_id,
        portfolio_id=state.portfolio_id,
        framework_id="dd_framework_v1",
        overall_score=round(bundle.overall_score, 2),
        overall_rag=score_to_rag(bundle.overall_score),
        category_summaries=category_summaries,
        assessments=assessments,
        recommendation=recommendation,
        narrative=narrative,
        hitl_required=hitl_required,
        hitl_reasons=hitl_reasons + veto_reasons,
    )


async def run_dd_pipeline(request: DDRequest) -> DDReport:
    """Entry point: runs the full due diligence pipeline end-to-end."""
    state = _build_initial_state(request)

    # Fan-out evidence + quant concurrently
    evidence_bundles, quant_bundle = await asyncio.gather(
        _gather_evidence(state),
        _run_quant(state),
    )

    # Assess all criteria
    bundle = await _assess(state, evidence_bundles, quant_bundle)

    # Update criterion states from assessment
    for score in bundle.criterion_scores:
        cs = state.criteria.get(score.criterion_id)
        if cs:
            cs.score = score.score
            cs.confidence = score.confidence
            cs.status = CriterionStatus.ASSESSED

    # Draft report
    draft = await _draft_report(state, bundle, quant_bundle, [])

    # QA pass (one revision if needed)
    qa_result = await _qa_check(state, draft, evidence_bundles, bundle)
    if not qa_result.get("approved", True) and state.iteration < 1:
        state.iteration += 1
        revision_notes = qa_result.get("revision_notes", [])
        draft = await _draft_report(state, bundle, quant_bundle, revision_notes)

    return _build_report(state, bundle, draft)


def create_agent() -> Agent:
    return Agent(
        name="DD Supervisor",
        description="Orchestrates the full portfolio due diligence pipeline.",
        model=BedrockModel(model_id=os.environ.get("DD_SUPERVISOR_MODEL_ID", "us.anthropic.claude-sonnet-5")),
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        callback_handler=None,
    )
