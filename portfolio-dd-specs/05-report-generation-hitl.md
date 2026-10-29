# Spec 05: Report Generation & HITL

Package: `wealth_management_portal.portfolio_dd` under `packages/portfolio_dd/`

---

## 1. Report Template — `dd_report.md.j2`

```jinja2
# Due Diligence Report: {{ manager_name }} — {{ portfolio_name }}
**Review Type:** {{ review_type }} | **Date:** {{ review_date }} | **Reviewer:** {{ reviewer_name }}
**Confidentiality:** Strictly Confidential — Investment Committee Use Only

---

## 1. Executive Summary

{{ executive_summary }}

**Overall Rating:** {{ overall_rating }} | **Recommendation:** {{ recommendation_label }}

| Category | Weight | Score | Weighted |
|---|---|---|---|
{% for cat in category_scores -%}
| {{ cat.name }} | {{ cat.weight | pct }} | {{ cat.score }}/5 | {{ cat.weighted | fmt2 }} |
{% endfor %}
**Composite Score:** {{ composite_score | fmt2 }} / 5.00

---

## 2. Manager Profile

| Field | Detail |
|---|---|
| Manager | {{ manager_name }} |
| ABN | {{ manager_abn }} |
| AFSL | {{ manager_afsl }} |
| AUM (AUD) | {{ manager_aum | aud }} |
| Inception Date | {{ portfolio_inception | audate }} |
| Benchmark | {{ benchmark_name }} |
| Strategy | {{ strategy_description }} |

---

## 3. Assessment Matrix

| Criterion | Category | Weight | Rating | Score | Evidence |{% if hitl_flags %} Flag |{% endif %}

|---|---|---|---|---|---|{% if hitl_flags %}---|{% endif %}

{% for c in criteria_assessments -%}
| {{ c.criterion_name }} | {{ c.category }} | {{ c.weight | pct }} | {{ c.rating }} | {{ c.score }}/5 | {{ c.evidence_count }} docs |{% if hitl_flags %} {{ c.flag_id | flag_icon }} |{% endif %}

{% endfor %}

---

## 4. Criterion Assessments

{% for c in criteria_assessments %}
### 4.{{ loop.index }}. {{ c.criterion_name }} ({{ c.weight | pct }} weight)

**Rating:** {{ c.rating }} | **Score:** {{ c.score }}/5

{{ c.narrative }}

**Key Evidence:**
{% for e in c.evidence_citations -%}
- [Source: {{ e.document }}, p.{{ e.page }} — "{{ e.quote }}"]
{% endfor %}
{% if c.flag_id %}
> **HITL Flag {{ c.flag_id }}:** {{ c.flag_reason }} — *{{ c.flag_status }}*
{% endif %}

{% endfor %}

---

## 5. Quantitative Analysis

### 5.1 Performance ({{ perf_period }})

| Metric | Portfolio | Benchmark | Excess |
|---|---|---|---|
| Return (ann.) | {{ perf.return_ann | pct }} | {{ perf.benchmark_return | pct }} | {{ perf.excess_return | pct }} |
| Volatility | {{ perf.volatility | pct }} | {{ perf.bench_volatility | pct }} | — |
| Sharpe Ratio | {{ perf.sharpe | fmt2 }} | {{ perf.bench_sharpe | fmt2 }} | — |
| Max Drawdown | {{ perf.max_drawdown | pct }} | {{ perf.bench_drawdown | pct }} | — |
| Tracking Error | {{ perf.tracking_error | pct }} | — | — |
| Info Ratio | {{ perf.info_ratio | fmt2 }} | — | — |

### 5.2 Attribution Summary

{{ attribution_narrative }}

---

## 6. Risk Summary

**Risk Rating:** {{ risk_rating }}

{% for r in key_risks %}
- **{{ r.category }}:** {{ r.description }} *(Severity: {{ r.severity }})*
{% endfor %}

---

## 7. Recommendation

**Decision:** {{ recommendation_label }}

{{ recommendation_rationale }}

**Conditions / Monitoring:**
{% for m in monitoring_requirements %}
- {{ m }}
{% endfor %}

**Next Review:** {{ next_review_date }}

---

## 8. Appendix

### A. Documents Reviewed
{% for d in documents_reviewed %}
- {{ d.name }} ({{ d.type }}, {{ d.date }})
{% endfor %}

### B. Audit Trail
{% for a in audit_entries %}
- {{ a.timestamp | audate }} — {{ a.user }}: {{ a.action }} on *{{ a.field }}*
  (was `{{ a.old_value }}`, now `{{ a.new_value }}`)
{% endfor %}

### C. Framework Version
DD Framework v{{ framework_version }} | Criteria set: {{ criteria_set_id }}
```

**Custom Jinja2 filters** (register in `ReportRendererService`):

```python
FILTERS = {
    "aud":    lambda v: f"A${v:,.0f}" if v else "N/A",
    "pct":    lambda v: f"{v:.1%}" if v is not None else "N/A",
    "fmt2":   lambda v: f"{v:.2f}" if v is not None else "N/A",
    "audate": lambda v: v.strftime("%-d %B %Y") if v else "N/A",
    "flag_icon": lambda fid: "⚑" if fid else "",
}
```

---

## 2. Report Drafter Agent

### System Prompt

```
You are a senior investment analyst drafting due diligence reports for an Australian wealth management
Investment Committee. Your output will be reviewed by the IC before any decision is made.

Tone: formal, measured, evidence-based. No marketing language. Australian English spelling.
Use passive constructions where appropriate ("it is noted that", "the Committee considers").

MANDATORY RULES:
1. Every factual claim must cite a source document using: [Source: <doc>, p.<N> — "<verbatim quote>"]
2. Never fabricate ratings, scores, or evidence. If evidence is absent, state "No evidence sighted."
3. Do not infer compliance status without citing an ASIC/APRA/ASX document.
4. Key Person Risk must reference named individuals only when named in source documents.
5. Return a valid JSON object matching ReportDrafterOutput — no prose outside the JSON.
```

### User Prompt

```python
USER_PROMPT_TEMPLATE = """
You are drafting narrative sections for a due diligence report.

## Review Context
```json
{review_context}
```

## Criteria Assessments (from framework engine)
```json
{criteria_assessments}
```

## Performance Data
```json
{performance_data}
```

Produce a JSON object with this exact structure:
{{
  "executive_summary": "<2-3 paragraph IC-level summary>",
  "recommendation_label": "<APPROVE | APPROVE WITH CONDITIONS | DEFER | REJECT>",
  "recommendation_rationale": "<paragraph>",
  "attribution_narrative": "<paragraph on performance drivers>",
  "risk_rating": "<LOW | MEDIUM | HIGH | CRITICAL>",
  "key_risks": [
    {{"category": "...", "description": "...", "severity": "LOW|MEDIUM|HIGH"}}
  ],
  "monitoring_requirements": ["..."],
  "criterion_narratives": {{
    "<criterion_id>": "<paragraph with inline citations>"
  }}
}}
Only return the JSON. No preamble, no commentary.
"""
```

### Pydantic Output Model

```python
from pydantic import BaseModel, Field
from typing import Literal

class KeyRisk(BaseModel):
    category: str
    description: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]

class ReportDrafterOutput(BaseModel):
    executive_summary: str
    recommendation_label: Literal["APPROVE", "APPROVE WITH CONDITIONS", "DEFER", "REJECT"]
    recommendation_rationale: str
    attribution_narrative: str
    risk_rating: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    key_risks: list[KeyRisk]
    monitoring_requirements: list[str]
    criterion_narratives: dict[str, str]  # criterion_id -> paragraph
```

---

## 3. Python Renderer — `ReportRendererService`

File: `packages/portfolio_dd/wealth_management_portal_portfolio_dd/renderer.py`

```python
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

from .models import DDReview, HITLFlag, ReportDrafterOutput

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "dd_report.md.j2"


def _aud(v):    return f"A${v:,.0f}" if v is not None else "N/A"
def _pct(v):    return f"{v:.1%}" if v is not None else "N/A"
def _fmt2(v):   return f"{v:.2f}" if v is not None else "N/A"
def _audate(v): return v.strftime("%-d %B %Y") if v else "N/A"
def _flag_icon(fid): return "⚑" if fid else ""


class ReportRendererService:
    def __init__(
        self,
        s3_bucket: str,
        kms_key_id: str,
        region: str = "ap-southeast-2",
    ):
        self.s3_bucket = s3_bucket
        self.kms_key_id = kms_key_id
        self.s3 = boto3.client("s3", region_name=region)
        self._env = self._build_jinja_env()

    def _build_jinja_env(self) -> Environment:
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape([]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.filters.update({
            "aud": _aud, "pct": _pct, "fmt2": _fmt2,
            "audate": _audate, "flag_icon": _flag_icon,
        })
        return env

    def build_context(
        self,
        review: DDReview,
        drafter_output: ReportDrafterOutput,
        hitl_flags: list[HITLFlag],
    ) -> dict[str, Any]:
        """Merge review data, drafter narratives, and HITL state into template context."""
        flag_by_criterion = {f.criterion_id: f for f in hitl_flags if f.criterion_id}

        criteria_assessments = []
        for ca in review.criteria_assessments:
            flag = flag_by_criterion.get(ca.criterion_id)
            narrative = drafter_output.criterion_narratives.get(ca.criterion_id, "")
            criteria_assessments.append({
                **ca.model_dump(),
                "narrative": narrative,
                "flag_id": flag.flag_id if flag else None,
                "flag_reason": flag.reason if flag else None,
                "flag_status": flag.status if flag else None,
            })

        return {
            # Manager / portfolio
            "manager_name": review.manager.name,
            "manager_abn": review.manager.abn,
            "manager_afsl": review.manager.afsl,
            "manager_aum": review.manager.aum_aud,
            "portfolio_name": review.portfolio.name,
            "portfolio_inception": review.portfolio.inception_date,
            "benchmark_name": review.portfolio.benchmark,
            "strategy_description": review.portfolio.strategy_description,
            # Review metadata
            "review_type": review.review_type,
            "review_date": datetime.now(timezone.utc),
            "reviewer_name": review.assigned_researcher,
            # Scores
            "overall_rating": review.overall_rating,
            "composite_score": review.composite_score,
            "category_scores": review.category_scores,
            "criteria_assessments": criteria_assessments,
            # Drafter output
            "executive_summary": drafter_output.executive_summary,
            "recommendation_label": drafter_output.recommendation_label,
            "recommendation_rationale": drafter_output.recommendation_rationale,
            "attribution_narrative": drafter_output.attribution_narrative,
            "risk_rating": drafter_output.risk_rating,
            "key_risks": [r.model_dump() for r in drafter_output.key_risks],
            "monitoring_requirements": drafter_output.monitoring_requirements,
            # Performance
            "perf_period": review.performance_period,
            "perf": review.performance_data,
            # HITL
            "hitl_flags": hitl_flags,
            # Appendix
            "documents_reviewed": review.documents_reviewed,
            "audit_entries": review.audit_log,
            "framework_version": review.framework_version,
            "criteria_set_id": review.criteria_set_id,
            "next_review_date": review.next_review_date,
        }

    def render(self, context: dict[str, Any]) -> str:
        """Render Jinja2 template to markdown string."""
        template = self._env.get_template(TEMPLATE_NAME)
        return template.render(**context)

    def save_to_s3(
        self,
        review_id: str,
        content: str,
        stage: str,  # "draft" | "final"
        version: int = 1,
    ) -> str:
        """Write KMS-encrypted report to S3. Returns s3:// URI."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        key = f"reports/{review_id}/{stage}/v{version}_{timestamp}.md"

        self.s3.put_object(
            Bucket=self.s3_bucket,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType="text/markdown",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=self.kms_key_id,
            Metadata={
                "review_id": review_id,
                "stage": stage,
                "version": str(version),
                "generated_at": timestamp,
            },
        )
        s3_uri = f"s3://{self.s3_bucket}/{key}"
        logger.info("Saved report", extra={"s3_uri": s3_uri, "stage": stage})
        return s3_uri
```

---

## 4. HITL State Machine

File: `packages/portfolio_dd/wealth_management_portal_portfolio_dd/hitl.py`

```python
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal

import boto3
from boto3.dynamodb.conditions import Attr
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trigger conditions — ALL are MANDATORY (must not be bypassed)
# ---------------------------------------------------------------------------
T1_RATING_CONFLICT = "T1_RATING_CONFLICT"
# Agent rating differs from keyword-rule baseline by >= 2 bands

T2_MISSING_EVIDENCE = "T2_MISSING_EVIDENCE"
# Criterion evidence_count == 0 (no documents cited)

T3_KEY_PERSON_HIGH = "T3_KEY_PERSON_HIGH"
# Key Person Risk criterion rated HIGH or CRITICAL

T4_COMPLIANCE_FINDING = "T4_COMPLIANCE_FINDING"
# Any regulatory/compliance citation references enforcement or breach

T5_LOW_COMPOSITE = "T5_LOW_COMPOSITE"
# Composite score < 2.5 (DEFER/REJECT threshold)


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------
class HITLStatus(str, Enum):
    PENDING    = "PENDING"
    IN_REVIEW  = "IN_REVIEW"
    APPROVED   = "APPROVED"
    OVERRIDDEN = "OVERRIDDEN"
    NOTED      = "NOTED"
    EVIDENCE_REQUESTED = "EVIDENCE_REQUESTED"
    CLOSED     = "CLOSED"


# ---------------------------------------------------------------------------
# Valid state transitions
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: dict[HITLStatus, set[HITLStatus]] = {
    HITLStatus.PENDING:    {HITLStatus.IN_REVIEW},
    HITLStatus.IN_REVIEW:  {
        HITLStatus.APPROVED,
        HITLStatus.OVERRIDDEN,
        HITLStatus.NOTED,
        HITLStatus.EVIDENCE_REQUESTED,
    },
    HITLStatus.EVIDENCE_REQUESTED: {HITLStatus.IN_REVIEW},
    HITLStatus.APPROVED:   {HITLStatus.CLOSED},
    HITLStatus.OVERRIDDEN: {HITLStatus.CLOSED},
    HITLStatus.NOTED:      {HITLStatus.CLOSED},
    HITLStatus.CLOSED:     set(),  # terminal
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class AuditLogEntry(BaseModel):
    timestamp: datetime
    user: str
    action: str
    field: str
    old_value: str | None
    new_value: str | None


class HITLFlag(BaseModel):
    flag_id: str
    review_id: str
    criterion_id: str | None = None
    trigger: Literal[
        "T1_RATING_CONFLICT",
        "T2_MISSING_EVIDENCE",
        "T3_KEY_PERSON_HIGH",
        "T4_COMPLIANCE_FINDING",
        "T5_LOW_COMPOSITE",
    ]
    reason: str
    status: HITLStatus = HITLStatus.PENDING
    ai_rating: str | None = None
    human_rating: str | None = None
    reviewer_note: str | None = None
    requires_response_by: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=48)
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    audit_log: list[AuditLogEntry] = Field(default_factory=list)


class ResolveRequest(BaseModel):
    action: Literal["approve_ai", "override_rating", "add_note", "request_evidence"]
    user: str
    human_rating: str | None = None
    note: str | None = None


# ---------------------------------------------------------------------------
# DynamoDB state machine
# ---------------------------------------------------------------------------
HITL_TABLE = "portfolio_dd_hitl_flags"  # PK: flag_id


def _target_status(action: str) -> HITLStatus:
    return {
        "approve_ai":       HITLStatus.APPROVED,
        "override_rating":  HITLStatus.OVERRIDDEN,
        "add_note":         HITLStatus.NOTED,
        "request_evidence": HITLStatus.EVIDENCE_REQUESTED,
    }[action]


def resolve_flag(
    flag: HITLFlag,
    request: ResolveRequest,
    dynamodb_resource: Any = None,
) -> HITLFlag:
    """Apply a researcher resolution to a HITL flag with DynamoDB conditional write."""
    if flag.status == HITLStatus.PENDING:
        # Auto-transition to IN_REVIEW on first resolution attempt
        flag.status = HITLStatus.IN_REVIEW

    target = _target_status(request.action)

    if target not in VALID_TRANSITIONS.get(flag.status, set()):
        raise ValueError(
            f"Invalid transition: {flag.status} -> {target} "
            f"(action={request.action})"
        )

    now = datetime.now(timezone.utc)
    old_rating = flag.ai_rating

    # Apply changes
    flag.status = target
    flag.resolved_at = now
    if request.human_rating:
        flag.human_rating = request.human_rating
    if request.note:
        flag.reviewer_note = request.note

    # Audit entry
    flag.audit_log.append(AuditLogEntry(
        timestamp=now,
        user=request.user,
        action=request.action,
        field="rating" if request.human_rating else "status",
        old_value=old_rating,
        new_value=request.human_rating or target.value,
    ))

    # Persist with optimistic lock on current status
    if dynamodb_resource:
        table = dynamodb_resource.Table(HITL_TABLE)
        table.update_item(
            Key={"flag_id": flag.flag_id},
            UpdateExpression=(
                "SET #s = :new_status, resolved_at = :ra, "
                "human_rating = :hr, reviewer_note = :rn, audit_log = :al"
            ),
            ConditionExpression=Attr("status").ne(HITLStatus.CLOSED.value),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":new_status": target.value,
                ":ra": now.isoformat(),
                ":hr": request.human_rating,
                ":rn": request.note,
                ":al": [e.model_dump(mode="json") for e in flag.audit_log],
            },
        )

    return flag
```

---

## 5. API Endpoints

File: `packages/portfolio_dd/wealth_management_portal_portfolio_dd/api.py`

```python
import asyncio
import logging
from typing import Annotated

import boto3
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path

from .hitl import HITLFlag, ResolveRequest, resolve_flag
from .models import DDReview, GenerateReportRequest, ReportResponse
from .renderer import ReportRendererService
from .service import DDReviewService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dd/reviews", tags=["portfolio-dd"])


def get_review_service() -> DDReviewService:
    return DDReviewService()   # wires DynamoDB, S3, Bedrock


def get_renderer() -> ReportRendererService:
    import os
    return ReportRendererService(
        s3_bucket=os.environ["DD_REPORTS_BUCKET"],
        kms_key_id=os.environ["DD_KMS_KEY_ID"],
    )


ReviewId = Annotated[str, Path(description="DD review UUID")]


# ---------------------------------------------------------------------------
# POST /dd/reviews/{id}/reports/generate
# ---------------------------------------------------------------------------
@router.post("/{review_id}/reports/generate", status_code=202)
async def generate_report(
    review_id: ReviewId,
    background_tasks: BackgroundTasks,
    svc: DDReviewService = Depends(get_review_service),
    renderer: ReportRendererService = Depends(get_renderer),
):
    """
    Kick off async report generation.
    1. Load review + assessments from DynamoDB.
    2. Invoke Report Drafter agent (Bedrock).
    3. Check HITL trigger conditions; create HITLFlag records if triggered.
    4. Render template + save draft to S3.
    Returns 202 immediately; poll GET /draft for status.
    """
    review = await svc.get_review(review_id)
    if not review:
        raise HTTPException(404, f"Review {review_id} not found")

    background_tasks.add_task(_generate_report_task, review_id, review, svc, renderer)
    return {"review_id": review_id, "status": "GENERATING", "message": "Report generation started"}


async def _generate_report_task(
    review_id: str,
    review: DDReview,
    svc: DDReviewService,
    renderer: ReportRendererService,
) -> None:
    try:
        await svc.update_report_status(review_id, "GENERATING")
        drafter_output = await svc.invoke_report_drafter(review)
        flags = await svc.evaluate_hitl_triggers(review)
        context = renderer.build_context(review, drafter_output, flags)
        markdown = renderer.render(context)
        s3_uri = renderer.save_to_s3(review_id, markdown, stage="draft")
        await svc.update_report_status(review_id, "DRAFT_READY", s3_uri=s3_uri, flags=flags)
    except Exception:
        logger.exception("Report generation failed", extra={"review_id": review_id})
        await svc.update_report_status(review_id, "GENERATION_FAILED")


# ---------------------------------------------------------------------------
# GET /dd/reviews/{id}/reports/draft
# ---------------------------------------------------------------------------
@router.get("/{review_id}/reports/draft")
async def get_draft_report(
    review_id: ReviewId,
    svc: DDReviewService = Depends(get_review_service),
) -> ReportResponse:
    """
    Poll report generation status and retrieve draft.
    Returns status + presigned S3 URL (1-hour expiry) + open HITL flags.
    """
    status = await svc.get_report_status(review_id)
    if not status:
        raise HTTPException(404, f"No report found for review {review_id}")

    presigned_url = None
    if status.s3_uri and status.report_status == "DRAFT_READY":
        presigned_url = svc.generate_presigned_url(status.s3_uri, expiry_seconds=3600)

    return ReportResponse(
        review_id=review_id,
        report_status=status.report_status,
        s3_uri=status.s3_uri,
        presigned_url=presigned_url,
        hitl_flags=status.open_flags,
        generated_at=status.generated_at,
    )


# ---------------------------------------------------------------------------
# POST /dd/reviews/{id}/hitl/{flag_id}/resolve
# ---------------------------------------------------------------------------
@router.post("/{review_id}/hitl/{flag_id}/resolve")
async def resolve_hitl_flag(
    review_id: ReviewId,
    flag_id: Annotated[str, Path(description="HITL flag UUID")],
    request: ResolveRequest,
    svc: DDReviewService = Depends(get_review_service),
) -> dict:
    """
    Researcher resolves a HITL flag.
    Actions: approve_ai | override_rating | add_note | request_evidence
    Returns the state transition that occurred so the UI updates without a separate status call.
    """
    flag = await svc.get_hitl_flag(flag_id)
    if not flag or flag.review_id != review_id:
        raise HTTPException(404, f"Flag {flag_id} not found for review {review_id}")

    ddb = boto3.resource("dynamodb")
    try:
        updated_flag = resolve_flag(flag, request, dynamodb_resource=ddb)
    except ValueError as e:
        raise HTTPException(409, str(e))

    return {
        "flag_id": flag_id,
        "previous_status": flag.status,
        "new_status": updated_flag.status,
        "action": request.action,
        "resolved_at": updated_flag.resolved_at.isoformat() if updated_flag.resolved_at else None,
    }


# ---------------------------------------------------------------------------
# GET /dd/reviews/{id}/reports/final
# ---------------------------------------------------------------------------
@router.get("/{review_id}/reports/final")
async def get_final_report(
    review_id: ReviewId,
    svc: DDReviewService = Depends(get_review_service),
    renderer: ReportRendererService = Depends(get_renderer),
) -> ReportResponse:
    """
    Retrieve finalised report after all HITL flags are CLOSED.
    If open flags remain, returns 409 with list of blocking flags.
    On first call with all flags resolved, regenerates final report with human overrides baked in.
    """
    open_flags = await svc.get_open_flags(review_id)
    if open_flags:
        raise HTTPException(409, {
            "message": "Open HITL flags must be resolved before finalising",
            "open_flags": [f.flag_id for f in open_flags],
        })

    status = await svc.get_report_status(review_id)
    if status and status.report_status == "FINAL_READY":
        presigned_url = svc.generate_presigned_url(status.final_s3_uri, expiry_seconds=3600)
        return ReportResponse(
            review_id=review_id,
            report_status="FINAL_READY",
            s3_uri=status.final_s3_uri,
            presigned_url=presigned_url,
            hitl_flags=[],
            generated_at=status.finalised_at,
        )

    # Re-render with human overrides applied
    review = await svc.get_review_with_overrides(review_id)
    drafter_output = await svc.invoke_report_drafter(review)
    context = renderer.build_context(review, drafter_output, [])
    markdown = renderer.render(context)
    final_uri = renderer.save_to_s3(review_id, markdown, stage="final")
    await svc.update_report_status(review_id, "FINAL_READY", final_s3_uri=final_uri)

    presigned_url = svc.generate_presigned_url(final_uri, expiry_seconds=3600)
    return ReportResponse(
        review_id=review_id,
        report_status="FINAL_READY",
        s3_uri=final_uri,
        presigned_url=presigned_url,
        hitl_flags=[],
    )
```

---

## 6. Demo Walkthrough — AMP Growth Fund ODD (15 minutes)

- **00:00** Open the Portfolio DD module from the wealth advisor sidebar; 5 sample portfolios listed.
- **00:30** Select "AMP Growth Fund" — status shows `INGESTION_COMPLETE`, 14 documents indexed.
- **01:00** Click "Run Due Diligence" — review type = ODD; confirm modal shown.
- **01:30** Agent activity stream opens: "Evaluating Investment Philosophy & Process..."
- **02:30** Assessment matrix populates live as each criterion scores in (10 criteria auto-resolved).
- **03:15** Key Person Risk criterion appears — rating `HIGH`, score `2/5`; HITL badge flashes amber.
- **03:30** T3 trigger fires (`T3_KEY_PERSON_HIGH`); flag `FLAG-001` created, status `PENDING`.
- **04:00** T2 trigger fires on Business Continuity (`T2_MISSING_EVIDENCE`, 0 docs cited); `FLAG-002` created.
- **04:30** "Generate Draft Report" button activates; POST `/dd/reviews/{id}/reports/generate` fires.
- **05:00** Spinner shows "Drafter agent synthesising narratives..."; 202 accepted.
- **06:00** Poll resolves — `DRAFT_READY`; draft report renders in split-pane markdown viewer.
- **06:30** HITL panel shows 2 open flags; overall recommendation is `DEFER` (composite = 2.4).
- **07:00** Researcher opens `FLAG-001` (Key Person Risk HIGH) — reads AI narrative, cites "no succession plan sighted".
- **07:45** Researcher confirms rating is correct; clicks "Approve AI Assessment" — action `approve_ai`.
- **08:00** FLAG-001 transitions `PENDING → IN_REVIEW → APPROVED → CLOSED`; badge turns green.
- **08:30** Researcher opens `FLAG-002` (Business Continuity, no evidence) — uploads BCP summary PDF.
- **09:30** Evidence re-ingested; criterion re-scored to `PASS`, score `3/5`; flag action = `override_rating`.
- **10:00** Human rating `PASS` saved; FLAG-002 status `OVERRIDDEN → CLOSED`.
- **10:30** All flags closed; "Finalise Report" button unlocks; POST `/dd/reviews/{id}/reports/final`.
- **11:00** Final report re-rendered: BCP now `3/5`, composite lifts to `2.8`, recommendation updates to `APPROVE WITH CONDITIONS`.
- **11:30** Audit trail section shows both researcher actions with timestamps and original AI values.
- **12:00** "Download PDF" triggers presigned URL (60-min expiry); board-ready PDF opens.
- **12:30** Review status flips to `COMPLETE`; AMP Growth Fund card in portfolio list shows green tick.
- **13:00** Facilitator walks back through HITL panel to show full state transition history.
- **14:00** Switch to "Pendal Australian Equities" to show zero-flag clean run (all criteria auto-resolved in 90s).
- **15:00** Q&A; demo ends with review archive showing 2 completed reviews and audit logs exportable to CSV.
