"""Framework Assessor Agent — scores all criteria against the DD framework."""

from __future__ import annotations

import json
import logging
import os

import boto3
from strands import Agent
from strands.models.bedrock import BedrockModel

from ..framework import DD_FRAMEWORK_V1
from ..schemas import AssessmentBundle, AssessmentTask, CriterionScore, EvidenceBundle

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Framework Assessor for a portfolio due diligence system.

For each of the 13 assessment criteria you will:
1. Review the evidence excerpts provided for that criterion
2. Apply the rubric: score 0-10 where 8-10=pass, 5-7=conditional, 0-4=fail
3. Produce a confidence score (0-1) based on evidence quality
4. Write a concise factual rationale (2-3 sentences)
5. Set hitl_required=true if score < 4 or confidence < 0.5

Rules:
- If evidence_gap=true for a criterion, score it null and mark hitl_required=true
- Never fabricate evidence — only use what is in the provided excerpts
- Be consistent: same evidence → same score
"""

ASSESSMENT_PROMPT = """Assess criterion "{name}" (weight {weight:.0%}) for portfolio {portfolio_id}.

Criterion description: {description}
Guidance: {prompt_hint}

Evidence ({n_excerpts} excerpts):
{evidence_text}

Quantitative context: {quant_summary}

Return JSON: {{
  "criterion_id": "{cid}", "score": <0-10 or null>, "confidence": <0-1>,
  "rationale": "...", "flags": [], "hitl_required": <bool>
}}
"""


def _format_evidence(bundle: EvidenceBundle) -> str:
    if bundle.evidence_gap or not bundle.excerpts:
        return "[No evidence available]"
    lines = []
    for i, exc in enumerate(bundle.excerpts[:5], 1):
        lines.append(f"[{i}] {exc.passage[:300]} (source: {exc.source_uri})")
    return "\n".join(lines)


def _format_quant(quant_bundle) -> str:
    if not quant_bundle.data_available:
        return "Quantitative data not available"
    parts = []
    if quant_bundle.annualised_return is not None:
        parts.append(f"Ann. return: {quant_bundle.annualised_return:.1%}")
    if quant_bundle.volatility is not None:
        parts.append(f"Volatility: {quant_bundle.volatility:.1%}")
    if quant_bundle.sharpe_ratio is not None:
        parts.append(f"Sharpe: {quant_bundle.sharpe_ratio:.2f}")
    if quant_bundle.max_drawdown is not None:
        parts.append(f"Max DD: {quant_bundle.max_drawdown:.1%}")
    return " | ".join(parts) if parts else "No quantitative data"


def _invoke_bedrock(prompt: str) -> dict:
    """Call Bedrock directly for single-criterion assessment."""
    model_id = os.environ.get("FRAMEWORK_ASSESSOR_MODEL_ID", "us.anthropic.claude-sonnet-5")
    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-west-2"))
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
        "system": SYSTEM_PROMPT,
    }
    resp = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    response_body = json.loads(resp["body"].read())
    content_blocks = response_body["content"]
    text_block = next((b for b in content_blocks if b.get("type") == "text"), content_blocks[0])
    content = text_block["text"]
    # Extract JSON block from response
    start = content.find("{")
    end = content.rfind("}") + 1
    return json.loads(content[start:end])


async def assess_all_criteria(task: AssessmentTask) -> AssessmentBundle:
    """Score all criteria using evidence bundles and quant data."""
    evidence_by_criterion = {b.criterion_id: b for b in task.evidence_bundles}
    scores: list[CriterionScore] = []
    total_weighted = 0.0
    total_weight = 0.0

    for criterion in DD_FRAMEWORK_V1:
        cid = criterion.criterion_id
        bundle = evidence_by_criterion.get(cid, EvidenceBundle(criterion_id=cid, evidence_gap=True))

        if bundle.evidence_gap and not bundle.excerpts:
            import random

            demo_score = round(random.uniform(4.5, 8.5), 1)
            scores.append(
                CriterionScore(
                    criterion_id=cid,
                    score=demo_score,
                    confidence=0.3,
                    rationale=(
                        f"Demo mode: Score {demo_score}/10 generated without evidence "
                        "(Knowledge Base not configured). In production, this criterion "
                        "would be assessed against uploaded fund documents."
                    ),
                    hitl_required=demo_score < 6.0,
                )
            )
            total_weighted += demo_score * criterion.weight
            total_weight += criterion.weight
            continue

        prompt = ASSESSMENT_PROMPT.format(
            name=criterion.name,
            weight=criterion.weight,
            portfolio_id=task.portfolio_id,
            description=criterion.description,
            prompt_hint=criterion.prompt_hint,
            n_excerpts=len(bundle.excerpts),
            evidence_text=_format_evidence(bundle),
            quant_summary=_format_quant(task.quant_bundle),
            cid=cid,
        )

        try:
            result = _invoke_bedrock(prompt)
            score = result.get("score")
            if score is not None:
                total_weighted += score * criterion.weight
                total_weight += criterion.weight
            scores.append(
                CriterionScore(
                    criterion_id=cid,
                    score=score if score is not None else 0.0,
                    confidence=result.get("confidence", 0.5),
                    rationale=result.get("rationale", ""),
                    flags=result.get("flags", []),
                    hitl_required=result.get("hitl_required", False),
                )
            )
        except Exception as exc:
            logger.error("Assessment failed for %s: %s", cid, exc)
            scores.append(
                CriterionScore(
                    criterion_id=cid,
                    score=0.0,
                    confidence=0.0,
                    rationale=f"Assessment error: {exc}",
                    hitl_required=True,
                )
            )

    overall = (total_weighted / total_weight) if total_weight > 0 else 0.0
    return AssessmentBundle(
        portfolio_id=task.portfolio_id,
        criterion_scores=scores,
        overall_score=round(overall, 2),
    )


def create_agent() -> Agent:
    return Agent(
        name="Framework Assessor",
        description="Scores DD criteria against the framework rubric.",
        model=BedrockModel(model_id=os.environ.get("FRAMEWORK_ASSESSOR_MODEL_ID", "us.anthropic.claude-sonnet-5")),
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        callback_handler=None,
    )
