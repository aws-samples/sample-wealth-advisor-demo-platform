"""Domain models for Portfolio Due Diligence."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, Field


class DDCategory(StrEnum):
    INVESTMENT_PROCESS = "investment_process"
    RISK_OPERATIONS = "risk_operations"
    COMPLIANCE_ESG = "compliance_esg"
    COMMERCIAL = "commercial"


class RAGStatus(StrEnum):
    RED = "red"
    AMBER = "amber"
    GREEN = "green"
    GREY = "grey"  # not yet assessed


class DDStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"


class AssetClass(StrEnum):
    AUSTRALIAN_EQUITIES = "australian_equities"
    GLOBAL_EQUITIES = "global_equities"
    FIXED_INCOME = "fixed_income"
    MULTI_ASSET = "multi_asset"
    ALTERNATIVES = "alternatives"
    INFRASTRUCTURE = "infrastructure"


class Rating(StrEnum):
    PASS = "pass"
    CONDITIONAL = "conditional"
    FAIL = "fail"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class InvestmentManager(BaseModel):
    manager_id: str = Field(default_factory=lambda: f"mgr_{uuid4().hex[:8]}")
    name: str
    afsl_number: str
    abn: str
    hq_city: str
    founded_year: int
    key_person: str
    aum_aud_bn: float
    website: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Portfolio(BaseModel):
    portfolio_id: str = Field(default_factory=lambda: f"pf_{uuid4().hex[:8]}")
    manager_id: str
    name: str
    apir_code: str
    asset_class: AssetClass
    benchmark: str
    inception_date: str  # ISO "YYYY-MM-DD"
    aum_aud_m: float
    fee_bps: int
    min_investment: int = 10_000
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AssessmentCriterion(BaseModel):
    criterion_id: str
    name: str
    category: DDCategory
    weight: Annotated[float, Field(gt=0, le=1)]
    description: str
    prompt_hint: str
    is_veto: bool = False  # single FAIL → overall FAIL


class DDSession(BaseModel):
    session_id: str = Field(default_factory=lambda: f"dd_{uuid4().hex[:8]}")
    portfolio_id: str
    portfolio_name: str
    manager_name: str
    framework_id: str = "dd_framework_v1"
    initiated_by: str
    status: DDStatus = DDStatus.PENDING
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    s3_report_key: str | None = None


class CriterionAssessment(BaseModel):
    assessment_id: str = Field(default_factory=lambda: f"ca_{uuid4().hex[:8]}")
    session_id: str
    criterion_id: str
    criterion_name: str = ""
    category: str = ""
    weight: float = 0.0
    confidence: float = 0.0
    rating: Rating = Rating.INSUFFICIENT_EVIDENCE
    rag_status: RAGStatus = RAGStatus.GREY
    score: float | None = None  # 0–10
    summary: str = ""
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)
    hitl_required: bool = False
    hitl_reason: str = ""
    agent_model_id: str = ""
    generated_at: datetime | None = None


class CategorySummary(BaseModel):
    category: DDCategory
    weight: float
    weighted_score: float
    rag_status: RAGStatus


class DDReport(BaseModel):
    report_id: str = Field(default_factory=lambda: f"rpt_{uuid4().hex[:8]}")
    session_id: str
    portfolio_id: str
    framework_id: str
    overall_score: float
    overall_rag: RAGStatus
    category_summaries: list[CategorySummary]
    assessments: list[CriterionAssessment]
    recommendation: str  # APPROVE / APPROVE_WITH_CONDITIONS / REJECT
    narrative: str
    hitl_required: bool = False
    hitl_reasons: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    s3_key: str = ""


class DocumentSource(BaseModel):
    doc_id: str = Field(default_factory=lambda: f"doc_{uuid4().hex[:8]}")
    portfolio_id: str
    doc_type: str  # "pds", "annual_report", "fsg", "factsheet", "other"
    filename: str
    s3_key: str
    page_count: int | None = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    kb_indexed: bool = False
