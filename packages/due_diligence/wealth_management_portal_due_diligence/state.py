"""AgentState — tracks per-criterion progress across a DD session."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CriterionStatus(StrEnum):
    PENDING = "pending"
    GATHERING = "gathering"
    ASSESSED = "assessed"
    FAILED = "failed"


@dataclass
class CriterionState:
    criterion_id: str
    category: str
    weight: float
    status: CriterionStatus = CriterionStatus.PENDING
    evidence_bundle: dict[str, Any] | None = None
    score: float | None = None
    confidence: float | None = None
    flags: list[str] = field(default_factory=list)


@dataclass
class AgentState:
    session_id: str
    portfolio_id: str
    portfolio_name: str
    manager_name: str
    criteria: dict[str, CriterionState] = field(default_factory=dict)
    quant_bundle: dict[str, Any] | None = None
    assessment_bundle: dict[str, Any] | None = None
    report_draft: dict[str, Any] | None = None
    qa_approved: bool = False
    qa_revision_notes: list[str] = field(default_factory=list)
    iteration: int = 0

    @property
    def overall_score(self) -> float | None:
        scored = [c for c in self.criteria.values() if c.score is not None]
        if not scored:
            return None
        total_weight = sum(c.weight for c in scored)
        if total_weight == 0:
            return None
        return sum(c.score * c.weight for c in scored) / total_weight

    @property
    def all_criteria_settled(self) -> bool:
        return all(c.status in (CriterionStatus.ASSESSED, CriterionStatus.FAILED) for c in self.criteria.values())

    @property
    def progress_pct(self) -> int:
        if not self.criteria:
            return 0
        settled = sum(
            1 for c in self.criteria.values() if c.status in (CriterionStatus.ASSESSED, CriterionStatus.FAILED)
        )
        return int(settled / len(self.criteria) * 100)
