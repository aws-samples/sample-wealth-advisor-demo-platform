"""Inter-agent message schemas (Pydantic v2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DDRequest(BaseModel):
    session_id: str
    portfolio_id: str
    portfolio_name: str
    manager_name: str
    criteria_ids: list[str] = Field(default_factory=list)  # empty = all 13


class EvidenceTask(BaseModel):
    session_id: str
    portfolio_id: str
    criterion_id: str
    criterion_label: str
    prompt_hint: str


class EvidenceExcerpt(BaseModel):
    doc_id: str
    passage: str
    source_uri: str
    relevance_score: float = 0.0


class EvidenceBundle(BaseModel):
    criterion_id: str
    excerpts: list[EvidenceExcerpt] = Field(default_factory=list)
    evidence_gap: bool = False


class QuantTask(BaseModel):
    session_id: str
    portfolio_id: str
    window_years: int = 3


class QuantBundle(BaseModel):
    portfolio_id: str
    annualised_return: float | None = None
    volatility: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    benchmark_excess_return: float | None = None
    attribution: dict[str, float] = Field(default_factory=dict)
    data_available: bool = True


class AssessmentTask(BaseModel):
    session_id: str
    portfolio_id: str
    evidence_bundles: list[EvidenceBundle]
    quant_bundle: QuantBundle


class CriterionScore(BaseModel):
    criterion_id: str
    score: float  # 0–10
    confidence: float  # 0–1
    rationale: str
    flags: list[str] = Field(default_factory=list)
    hitl_required: bool = False


class AssessmentBundle(BaseModel):
    portfolio_id: str
    criterion_scores: list[CriterionScore]
    overall_score: float


class DraftTask(BaseModel):
    session_id: str
    portfolio_id: str
    portfolio_name: str
    manager_name: str
    assessment_bundle: AssessmentBundle
    quant_bundle: QuantBundle
    revision_notes: list[str] = Field(default_factory=list)


class ReportSection(BaseModel):
    category: str
    title: str
    content: str
    # Descriptive metadata (which criteria this section covers). The report
    # drafter's LLM sometimes omits it; default to empty so one missing field
    # does not fail validation and collapse the entire report draft.
    criteria_covered: list[str] = Field(default_factory=list)


class ReportDraft(BaseModel):
    portfolio_id: str
    overall_score: float
    recommendation: str  # "APPROVE" | "APPROVE_WITH_CONDITIONS" | "REJECT"
    sections: list[ReportSection]
    executive_summary: str
    generated_at: str


class QATask(BaseModel):
    session_id: str
    report_draft: ReportDraft
    evidence_bundles: list[EvidenceBundle]
    assessment_bundle: AssessmentBundle


class QAResult(BaseModel):
    approved: bool
    revision_notes: list[str] = Field(default_factory=list)
    confidence_score: float = 1.0


class DDAgentResult(BaseModel):
    session_id: str
    portfolio_id: str
    portfolio_name: str
    report: Any  # DDReport dict at runtime
    qa_iterations: int
    status: str  # "complete" | "failed"
    error: str | None = None


# ── SSE streaming event ───────────────────────────────────────────────────────


class DDProgressEvent(BaseModel):
    """Emitted over SSE to update the UI during a live DD run."""

    session_id: str
    event_type: str  # "criterion_started" | "criterion_complete" | "report_ready" | "hitl_flag" | "error"
    criterion_id: str | None = None
    criterion_name: str | None = None
    rag_status: str | None = None
    score: float | None = None
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
