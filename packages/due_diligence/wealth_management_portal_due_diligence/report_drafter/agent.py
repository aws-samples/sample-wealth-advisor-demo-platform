"""Report Drafter Agent — generates the board-ready DD report narrative."""

from __future__ import annotations

import json
import logging
import os

import boto3
from strands import Agent
from strands.models.bedrock import BedrockModel

from ..schemas import DraftTask, ReportDraft, ReportSection

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Report Drafter for a portfolio due diligence system.

Write professional board-ready due diligence report sections from scored criteria and evidence.
Follow Australian Investment Committee language standards:
- Formal, precise, auditor-ready prose
- Present tense for current assessments
- Evidence-grounded — cite [Source: doc, p.N] for specific claims
- Flag criteria rated below 5/10 with conditions or recommendations

Structure your output as a JSON ReportDraft with sections for each of the four categories plus an executive summary.
"""


def _build_draft_prompt(task: DraftTask) -> str:
    scores_table = "\n".join(
        f"- {s.criterion_id}: {s.score:.1f}/10 (confidence {s.confidence:.0%}) — {s.rationale[:100]}"
        for s in task.assessment_bundle.criterion_scores
    )
    quant_summary = ""
    q = task.quant_bundle
    if q.data_available:
        parts = []
        if q.annualised_return is not None:
            parts.append(f"ann. return {q.annualised_return:.1%}")
        if q.sharpe_ratio is not None:
            parts.append(f"Sharpe {q.sharpe_ratio:.2f}")
        if q.max_drawdown is not None:
            parts.append(f"max DD {q.max_drawdown:.1%}")
        quant_summary = " | ".join(parts)

    revision_block = ""
    if task.revision_notes:
        revision_block = "\n\nREVISION NOTES FROM QA:\n" + "\n".join(f"- {n}" for n in task.revision_notes)

    header = (
        f"Draft a Due Diligence report for {task.portfolio_name} ({task.portfolio_id}), managed by {task.manager_name}."
    )
    return f"""{header}

Criterion scores:
{scores_table}

Quantitative: {quant_summary or "Not available"}
Overall score: {task.assessment_bundle.overall_score:.1f}/10
Recommendation: {_infer_recommendation(task.assessment_bundle.overall_score)}{revision_block}

Return JSON matching this schema exactly:
{{
  "portfolio_id": "{task.portfolio_id}",
  "overall_score": {task.assessment_bundle.overall_score},
  "recommendation": "<APPROVE|APPROVE_WITH_CONDITIONS|REJECT>",
  "executive_summary": "<2-3 paragraph executive summary>",
  "sections": [
    {{"category": "investment_process", "title": "Investment Process",
      "content": "<narrative>", "criteria_covered": ["ip_01","ip_02","ip_03","ip_04"]}},
    {{"category": "risk_operations", "title": "Risk & Operations",
      "content": "<narrative>", "criteria_covered": ["ro_01","ro_02","ro_03","ro_04"]}},
    {{"category": "compliance_esg", "title": "Compliance & ESG",
      "content": "<narrative>", "criteria_covered": ["ce_01","ce_02","ce_03"]}},
    {{"category": "commercial", "title": "Commercial",
      "content": "<narrative>", "criteria_covered": ["co_01","co_02"]}}
  ],
  "generated_at": "<ISO timestamp>"
}}"""


def _infer_recommendation(score: float) -> str:
    if score >= 7.0:
        return "APPROVE"
    if score >= 4.0:
        return "APPROVE_WITH_CONDITIONS"
    return "REJECT"


def _invoke_bedrock(prompt: str) -> dict:
    model_id = os.environ.get("REPORT_DRAFTER_MODEL_ID", "us.anthropic.claude-sonnet-5")
    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-west-2"))
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
        "system": SYSTEM_PROMPT,
    }
    resp = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(resp["body"].read())
    text_block = next((b for b in result["content"] if b.get("type") == "text"), None)
    content = text_block["text"] if text_block else ""
    start = content.find("{")
    end = content.rfind("}") + 1
    return json.loads(content[start:end]) if start >= 0 and end > start else {"narrative": content}


async def draft_report(task: DraftTask) -> ReportDraft:
    prompt = _build_draft_prompt(task)
    try:
        result = _invoke_bedrock(prompt)
        # Parse sections resiliently: a single malformed section (e.g. the LLM
        # omitting a required field) must not discard the entire report draft.
        sections = []
        for s in result.get("sections", []):
            try:
                sections.append(ReportSection(**s))
            except Exception as sec_exc:
                cat = s.get("category") if isinstance(s, dict) else s
                logger.warning("Skipping malformed report section %r: %s", cat, sec_exc)
        from datetime import datetime

        return ReportDraft(
            portfolio_id=task.portfolio_id,
            overall_score=result.get("overall_score", task.assessment_bundle.overall_score),
            recommendation=result.get("recommendation", _infer_recommendation(task.assessment_bundle.overall_score)),
            sections=sections,
            executive_summary=result.get("executive_summary", ""),
            generated_at=result.get("generated_at", datetime.utcnow().isoformat()),
        )
    except Exception as exc:
        logger.error("Report drafting failed: %s", exc)
        from datetime import datetime

        return ReportDraft(
            portfolio_id=task.portfolio_id,
            overall_score=task.assessment_bundle.overall_score,
            recommendation=_infer_recommendation(task.assessment_bundle.overall_score),
            sections=[],
            executive_summary=f"Report generation encountered an error: {exc}",
            generated_at=datetime.utcnow().isoformat(),
        )


def create_agent() -> Agent:
    return Agent(
        name="Report Drafter",
        description="Generates board-ready DD report narrative.",
        model=BedrockModel(model_id=os.environ.get("REPORT_DRAFTER_MODEL_ID", "us.anthropic.claude-sonnet-5")),
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        callback_handler=None,
    )
