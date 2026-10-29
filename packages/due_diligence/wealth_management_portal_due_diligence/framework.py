"""DD Framework v1.0 — 13 criteria, weights summing to 1.0."""

from __future__ import annotations

from .models import AssessmentCriterion, DDCategory, RAGStatus

DD_FRAMEWORK_V1: list[AssessmentCriterion] = [
    # ── Investment Process (30%) ──────────────────────────────────────────────
    AssessmentCriterion(
        criterion_id="ip_01",
        name="Investment Philosophy & Process",
        category=DDCategory.INVESTMENT_PROCESS,
        weight=0.10,
        description="Clarity, consistency, and competitive edge of the investment philosophy",
        prompt_hint="Review PDS sections on investment approach, philosophy statement, and any CIO letters. "
        "Look for explicit alpha sources, constraints, and process evolution narrative.",
    ),
    AssessmentCriterion(
        criterion_id="ip_02",
        name="Portfolio Construction",
        category=DDCategory.INVESTMENT_PROCESS,
        weight=0.08,
        description="Systematic approach to position sizing, concentration limits, and diversification",
        prompt_hint="Examine portfolio construction rules, concentration limits (max single stock %, sector caps), "
        "and any documented deviation history.",
    ),
    AssessmentCriterion(
        criterion_id="ip_03",
        name="Performance Attribution",
        category=DDCategory.INVESTMENT_PROCESS,
        weight=0.07,
        description="Quality and transparency of performance attribution reporting",
        prompt_hint="Look for Brinson attribution tables, factor decomposition, and tracking error disclosure. "
        "Check if attribution is audited or third-party verified.",
    ),
    AssessmentCriterion(
        criterion_id="ip_04",
        name="Benchmark Appropriateness",
        category=DDCategory.INVESTMENT_PROCESS,
        weight=0.05,
        description="Whether the stated benchmark reflects true investment universe and mandate",
        prompt_hint="Compare benchmark to actual portfolio holdings and stated asset class mandate. "
        "Flag if benchmark was changed in last 3 years.",
    ),
    # ── Risk & Operations (30%) ───────────────────────────────────────────────
    AssessmentCriterion(
        criterion_id="ro_01",
        name="Risk Management Framework",
        category=DDCategory.RISK_OPERATIONS,
        weight=0.10,
        description="Robustness of risk controls, limits, and governance structures",
        prompt_hint="Identify risk committee structure, VaR/CVaR limits, drawdown triggers, and escalation "
        "procedures. Check for independent risk function.",
    ),
    AssessmentCriterion(
        criterion_id="ro_02",
        name="Operational Infrastructure",
        category=DDCategory.RISK_OPERATIONS,
        weight=0.08,
        description="Quality of middle/back-office systems, custody, and technology stack",
        prompt_hint="Check custodian details (APRA-regulated?), OMS/PMS systems, reconciliation processes, "
        "and most recent external audit outcomes.",
    ),
    AssessmentCriterion(
        criterion_id="ro_03",
        name="Key Person Risk",
        category=DDCategory.RISK_OPERATIONS,
        weight=0.07,
        description="Concentration of investment capability in specific individuals",
        prompt_hint="Identify named portfolio managers and any key-person clauses in PDS. "
        "Look for succession plan, team depth, and average tenure.",
        is_veto=False,
    ),
    AssessmentCriterion(
        criterion_id="ro_04",
        name="Business Continuity",
        category=DDCategory.RISK_OPERATIONS,
        weight=0.05,
        description="BCP/DR capabilities and testing frequency",
        prompt_hint="Look for BCP policy references, RTO/RPO statements, and disaster recovery test evidence. "
        "COVID-era disclosures are acceptable evidence.",
    ),
    # ── Compliance & ESG (25%) ────────────────────────────────────────────────
    AssessmentCriterion(
        criterion_id="ce_01",
        name="Regulatory Compliance",
        category=DDCategory.COMPLIANCE_ESG,
        weight=0.12,
        description="AFSL obligations, ASIC breach history, and internal compliance program",
        prompt_hint="Verify AFSL number is current, check for disclosed ASIC enforceable undertakings, "
        "review compliance framework section and breach register reference.",
        is_veto=True,  # any FAIL here → overall FAIL
    ),
    AssessmentCriterion(
        criterion_id="ce_02",
        name="ESG Integration",
        category=DDCategory.COMPLIANCE_ESG,
        weight=0.08,
        description="Depth and authenticity of ESG integration in investment process",
        prompt_hint="Look for UNPRI signatory status, exclusion lists, ESG scoring methodology, "
        "stewardship policy, and engagement/voting disclosures.",
    ),
    AssessmentCriterion(
        criterion_id="ce_03",
        name="Conflicts of Interest",
        category=DDCategory.COMPLIANCE_ESG,
        weight=0.05,
        description="Identification, disclosure, and management of conflicts",
        prompt_hint="Review related-party transaction policy, soft-dollar disclosure, "
        "personal trading policy, and board/IC independence.",
    ),
    # ── Commercial (15%) ──────────────────────────────────────────────────────
    AssessmentCriterion(
        criterion_id="co_01",
        name="Fee Transparency",
        category=DDCategory.COMMERCIAL,
        weight=0.08,
        description="All-in cost clarity including base fee, performance fee, and transaction costs",
        prompt_hint="Extract MER, ICR, performance fee hurdle and rate, buy/sell spread, "
        "and any indirect costs (underlying fund fees for fund-of-funds).",
    ),
    AssessmentCriterion(
        criterion_id="co_02",
        name="Business Viability",
        category=DDCategory.COMMERCIAL,
        weight=0.07,
        description="Manager financial stability, AUM trajectory, and ownership structure",
        prompt_hint="Look for parent company ownership, AUM growth trend (3-year), "
        "staff retention disclosures, and any wind-down risk indicators.",
    ),
]

assert abs(sum(c.weight for c in DD_FRAMEWORK_V1) - 1.0) < 1e-9, "Framework weights must sum to 1.0"

FRAMEWORK_BY_ID: dict[str, AssessmentCriterion] = {c.criterion_id: c for c in DD_FRAMEWORK_V1}
VETO_CRITERION_IDS: set[str] = {c.criterion_id for c in DD_FRAMEWORK_V1 if c.is_veto}


def score_to_rag(score: float | None) -> RAGStatus:
    """Map a 0–10 score to RAG status."""
    if score is None:
        return RAGStatus.GREY
    if score >= 7.0:
        return RAGStatus.GREEN
    if score >= 4.0:
        return RAGStatus.AMBER
    return RAGStatus.RED


def compute_overall_recommendation(
    assessments: list,
    weighted_score: float,
) -> tuple[str, list[str]]:
    """Return (recommendation_label, hitl_reasons).

    Logic:
    - Any veto criterion rated FAIL → REJECT
    - weighted_score >= 7.0 → APPROVE
    - weighted_score >= 4.0 → APPROVE_WITH_CONDITIONS
    - weighted_score < 4.0 → REJECT
    HITL triggers: see is_hitl_required().
    """
    reasons: list[str] = []
    veto_failed = [
        a.criterion_id
        for a in assessments
        if a.criterion_id in VETO_CRITERION_IDS and a.score is not None and a.score < 4.0
    ]
    if veto_failed:
        reasons.append(f"Veto criterion failed: {', '.join(veto_failed)}")
        return "REJECT", reasons

    if weighted_score >= 7.0:
        recommendation = "APPROVE"
    elif weighted_score >= 4.0:
        recommendation = "APPROVE_WITH_CONDITIONS"
    else:
        recommendation = "REJECT"

    return recommendation, reasons


# HITL trigger conditions (any → flag for human review)
HITL_TRIGGERS = [
    ("low_score", "Any criterion score < 4.0"),
    ("insufficient_evidence", "Any criterion rated INSUFFICIENT_EVIDENCE on weight >= 7%"),
    ("key_person_amber", "Key Person Risk (ro_03) rated AMBER or worse"),
    ("veto_criterion", "Veto criterion (ce_01) is not GREEN"),
    ("reject_recommendation", "Overall recommendation is REJECT"),
]


def is_hitl_required(assessments: list, recommendation: str) -> tuple[bool, list[str]]:
    """Return (hitl_required, reasons)."""
    reasons: list[str] = []

    for a in assessments:
        if a.score is not None and a.score < 4.0:
            reasons.append(f"Low score on {a.criterion_id}: {a.score:.1f}")
        criterion = FRAMEWORK_BY_ID.get(a.criterion_id)
        if a.score is None and criterion and criterion.weight >= 0.07:
            reasons.append(f"Insufficient evidence for high-weight criterion {a.criterion_id}")

    kpr = next((a for a in assessments if a.criterion_id == "ro_03"), None)
    if kpr and kpr.rag_status in (RAGStatus.AMBER, RAGStatus.RED):
        reasons.append("Key Person Risk is AMBER or RED")

    reg = next((a for a in assessments if a.criterion_id == "ce_01"), None)
    if reg and reg.rag_status != RAGStatus.GREEN:
        reasons.append("Regulatory Compliance is not GREEN")

    if recommendation == "REJECT":
        reasons.append("Overall recommendation is REJECT")

    return bool(reasons), reasons
