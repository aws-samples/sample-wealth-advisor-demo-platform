# Spec 04: Due Diligence Framework Engine

**Package:** `wealth_management_portal.portfolio_dd` → `packages/portfolio_dd/`
**Lambda handler:** `portfolio_dd.handler` | **Agent:** Strands SDK + Bedrock AgentCore

---

## 1. Framework Pydantic Models

```python
# packages/portfolio_dd/src/wealth_management_portal/portfolio_dd/models.py
from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal

class Category(str, Enum):
    INVESTMENT_PROCESS = "investment_process"
    RISK_OPERATIONS    = "risk_operations"
    COMPLIANCE_ESG     = "compliance_esg"
    COMMERCIAL         = "commercial"

class Rating(str, Enum):
    PASS                 = "pass"
    CONDITIONAL          = "conditional"
    FAIL                 = "fail"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"

class CriterionRubric(BaseModel):
    pass_indicators:        list[str]
    conditional_indicators: list[str]
    fail_indicators:        list[str]
    insufficient_indicators: list[str]

class AssessmentCriterion(BaseModel):
    id:       str
    name:     str
    category: Category
    weight:   float          # 0-1, sum across all = 1.0
    rubric:   CriterionRubric
    is_veto:  bool = False   # True → single FAIL = overall FAIL

class CriterionResult(BaseModel):
    criterion_id: str
    rating:       Rating
    score:        float | None   # None if INSUFFICIENT_EVIDENCE
    rationale:    str
    evidence_refs: list[str]     # S3 keys or doc IDs
    hitl_required: bool = False

class PortfolioDDResult(BaseModel):
    portfolio_id:           str
    framework_version:      Literal["v1"] = "v1"
    criterion_results:      list[CriterionResult]
    weighted_score:         float | None
    overall_recommendation: Literal["approve","conditional_approve","reject","refer_to_committee"]
    veto_triggers:          list[str]
    hitl_required:          bool
    hitl_reasons:           list[str]
    assessor_notes:         str = ""

# ── Framework instantiation ───────────────────────────────────────────────────

FRAMEWORK_V1: list[AssessmentCriterion] = [
    # ── Investment Process (30%) ──────────────────────────────────────────────
    AssessmentCriterion(
        id="IP-01", name="Investment Philosophy & Process", category=Category.INVESTMENT_PROCESS,
        weight=0.10, is_veto=False,
        rubric=CriterionRubric(
            pass_indicators=[
                "Documented IPS with clear alpha sources and constraints",
                "Consistent process application evidenced across market cycles",
                "Portfolio manager articulates edge with quantitative support",
            ],
            conditional_indicators=[
                "IPS exists but contains ambiguous language around execution",
                "Process applied inconsistently in 1-2 documented instances",
            ],
            fail_indicators=[
                "No formal IPS or investment mandate document",
                "Process materially changed without stakeholder disclosure",
            ],
            insufficient_indicators=[
                "IPS not provided; verbal description only",
                "Document version predates fund launch by >3 years with no update",
            ],
        ),
    ),
    AssessmentCriterion(
        id="IP-02", name="Portfolio Construction", category=Category.INVESTMENT_PROCESS,
        weight=0.08, is_veto=False,
        rubric=CriterionRubric(
            pass_indicators=[
                "Explicit position sizing rules with documented rationale",
                "Concentration limits enforced and monitored systematically",
                "Sector/factor tilts explained and within mandate",
            ],
            conditional_indicators=[
                "Sizing rules informal but consistently applied in practice",
                "Single position breached limit on ≤2 occasions with remediation",
            ],
            fail_indicators=[
                "No documented position sizing or concentration guidelines",
                "Persistent concentration breaches without remediation",
            ],
            insufficient_indicators=[
                "Only aggregate-level holdings data provided; no construction methodology",
            ],
        ),
    ),
    AssessmentCriterion(
        id="IP-03", name="Performance Attribution", category=Category.INVESTMENT_PROCESS,
        weight=0.07, is_veto=False,
        rubric=CriterionRubric(
            pass_indicators=[
                "Brinson-Hood-Beebower or factor-model attribution run monthly",
                "Attribution shared with investors in quarterly reports",
                "Stock selection vs allocation effect clearly separated",
            ],
            conditional_indicators=[
                "Attribution run quarterly, not monthly",
                "Attribution methodology not independently validated",
            ],
            fail_indicators=[
                "No formal attribution process in place",
                "Performance claimed without attribution evidence",
            ],
            insufficient_indicators=[
                "Attribution reports not provided for review",
                "Fund < 12 months old; insufficient history",
            ],
        ),
    ),
    AssessmentCriterion(
        id="IP-04", name="Benchmark Appropriateness", category=Category.INVESTMENT_PROCESS,
        weight=0.05, is_veto=False,
        rubric=CriterionRubric(
            pass_indicators=[
                "Benchmark reflects actual investable universe and mandate constraints",
                "Tracking error vs benchmark consistent with active risk budget",
            ],
            conditional_indicators=[
                "Benchmark broad but defensible; minor mismatch documented",
                "TE vs benchmark elevated but manager has written justification",
            ],
            fail_indicators=[
                "Benchmark materially inconsistent with portfolio construction",
                "Manager cherry-picks benchmark to flatter performance",
            ],
            insufficient_indicators=[
                "No benchmark specified in mandate documents",
            ],
        ),
    ),
    # ── Risk & Operations (30%) ───────────────────────────────────────────────
    AssessmentCriterion(
        id="RO-01", name="Risk Management Framework", category=Category.RISK_OPERATIONS,
        weight=0.10, is_veto=True,
        rubric=CriterionRubric(
            pass_indicators=[
                "Independent risk function separate from portfolio management",
                "Daily VaR / CVaR monitoring with breach escalation procedures",
                "Liquidity stress testing performed at least quarterly",
            ],
            conditional_indicators=[
                "Risk oversight exists but reports to PM; independence gap noted",
                "Stress testing performed annually only",
            ],
            fail_indicators=[
                "No independent risk oversight function",
                "Multiple material risk limit breaches without documented remediation",
            ],
            insufficient_indicators=[
                "Risk policy document not provided",
            ],
        ),
    ),
    AssessmentCriterion(
        id="RO-02", name="Operational Infrastructure", category=Category.RISK_OPERATIONS,
        weight=0.08, is_veto=False,
        rubric=CriterionRubric(
            pass_indicators=[
                "PAS/OMS and portfolio accounting systems tier-1 or equivalent",
                "Custodian independent of manager with daily reconciliation",
                "SSAE 18 / ISAE 3402 SOC 1 or SOC 2 report available",
            ],
            conditional_indicators=[
                "Reconciliation performed weekly rather than daily",
                "SOC report available but >18 months old",
            ],
            fail_indicators=[
                "No independent custodian arrangement",
                "Reconciliation failures unresolved >30 days",
            ],
            insufficient_indicators=[
                "Service provider list not disclosed",
            ],
        ),
    ),
    AssessmentCriterion(
        id="RO-03", name="Key Person Risk", category=Category.RISK_OPERATIONS,
        weight=0.07, is_veto=False,
        rubric=CriterionRubric(
            pass_indicators=[
                "Team depth ≥3 senior investment professionals",
                "Key-person clause in PDS with defined investor notification rights",
                "Succession plan documented and tested",
            ],
            conditional_indicators=[
                "2-person team with documented succession; tenure stable >5 years",
                "Key-person clause absent but fund size <$100M AUM",
            ],
            fail_indicators=[
                "Single decision-maker with no succession plan or team depth",
                "Key-person departed within last 12 months without notification",
            ],
            insufficient_indicators=[
                "Org chart not provided; team composition unclear",
            ],
        ),
    ),
    AssessmentCriterion(
        id="RO-04", name="Business Continuity", category=Category.RISK_OPERATIONS,
        weight=0.05, is_veto=False,
        rubric=CriterionRubric(
            pass_indicators=[
                "BCP/DR plan tested annually with documented results",
                "RPO ≤4h, RTO ≤8h for critical systems",
            ],
            conditional_indicators=[
                "BCP exists but last test >18 months ago",
                "RTO >8h but <24h with remediation plan",
            ],
            fail_indicators=[
                "No BCP/DR plan documented",
                "Critical system failure in past 24 months with no post-mortem",
            ],
            insufficient_indicators=[
                "BCP document not provided for review",
            ],
        ),
    ),
    # ── Compliance & ESG (25%) ────────────────────────────────────────────────
    AssessmentCriterion(
        id="CE-01", name="Regulatory Compliance", category=Category.COMPLIANCE_ESG,
        weight=0.12, is_veto=True,
        rubric=CriterionRubric(
            pass_indicators=[
                "AFSL in good standing; no conditions, bans, or enforceable undertakings",
                "Compliance framework with annual board sign-off",
                "No material ASIC/APRA findings in last 3 years",
            ],
            conditional_indicators=[
                "Minor breach recorded; remediated within 90 days; ASIC notified",
                "RG 97 fee disclosure minor non-compliance; corrective PDS issued",
            ],
            fail_indicators=[
                "AFSL suspended, cancelled, or under conditions",
                "Criminal conviction or enforceable undertaking within 5 years",
                "Material breach unremediated",
            ],
            insufficient_indicators=[
                "AFSL number not provided for verification",
            ],
        ),
    ),
    AssessmentCriterion(
        id="CE-02", name="ESG Integration", category=Category.COMPLIANCE_ESG,
        weight=0.08, is_veto=False,
        rubric=CriterionRubric(
            pass_indicators=[
                "Formal ESG policy integrated into investment process (not overlay)",
                "Signatory to UNPRI with public disclosure",
                "ESG data provider + scoring methodology documented",
            ],
            conditional_indicators=[
                "ESG considered but no formal policy; manager in process of formalising",
                "UNPRI signatory but reporting compliance partial",
            ],
            fail_indicators=[
                "ESG excluded entirely from process with no disclosure",
                "Greenwashing risk: ESG claims not supported by investment evidence",
            ],
            insufficient_indicators=[
                "ESG policy requested but not provided",
            ],
        ),
    ),
    AssessmentCriterion(
        id="CE-03", name="Conflicts of Interest", category=Category.COMPLIANCE_ESG,
        weight=0.05, is_veto=False,
        rubric=CriterionRubric(
            pass_indicators=[
                "Conflicts register maintained and reviewed by board/compliance",
                "Related-party transactions disclosed in PDS and periodic reports",
            ],
            conditional_indicators=[
                "Conflicts register exists but last reviewed >12 months ago",
                "One undisclosed related-party transaction; remediated",
            ],
            fail_indicators=[
                "No conflicts register or policy",
                "Material undisclosed conflict involving portfolio decisions",
            ],
            insufficient_indicators=[
                "FSG / Conflicts disclosure not provided",
            ],
        ),
    ),
    # ── Commercial (15%) ─────────────────────────────────────────────────────
    AssessmentCriterion(
        id="CO-01", name="Fee Transparency", category=Category.COMMERCIAL,
        weight=0.08, is_veto=False,
        rubric=CriterionRubric(
            pass_indicators=[
                "RG 97 ICR and MER disclosed; all fee components itemised",
                "Performance fee (if any) with clear high-water mark and hurdle",
            ],
            conditional_indicators=[
                "Fees disclosed but indirect costs estimate methodology unclear",
                "Performance fee hurdle below benchmark return",
            ],
            fail_indicators=[
                "Fee schedule incomplete; hidden costs identified",
                "Fees materially misrepresented vs PDS disclosures",
            ],
            insufficient_indicators=[
                "Current PDS not provided; only historical fee schedule",
            ],
        ),
    ),
    AssessmentCriterion(
        id="CO-02", name="Business Viability", category=Category.COMMERCIAL,
        weight=0.07, is_veto=False,
        rubric=CriterionRubric(
            pass_indicators=[
                "AUM >$100M or parent entity provides balance-sheet backing",
                "Revenue covers operating costs; 3-year audited P&L available",
                "No going-concern qualification in last audit",
            ],
            conditional_indicators=[
                "AUM $50–100M; trajectory positive; 2 years runway at current burn",
                "Single large mandate represents >40% AUM; redemption risk noted",
            ],
            fail_indicators=[
                "Going-concern qualification in most recent audit",
                "AUM <$50M with negative AUM trend over 12 months",
            ],
            insufficient_indicators=[
                "Financial statements not provided",
            ],
        ),
    ),
]

CRITERION_MAP: dict[str, AssessmentCriterion] = {c.id: c for c in FRAMEWORK_V1}
```

---

## 2. Rating Rubrics

*(12 tables — one per criterion)*

**IP-01 Investment Philosophy & Process**
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| Documented IPS with clear alpha sources | IPS exists but contains ambiguous execution language | No formal IPS or mandate document | IPS not provided; verbal description only |
| Consistent process across market cycles | Process inconsistently applied in 1–2 instances | Process materially changed without disclosure | Document predates fund launch >3 years, no update |
| Manager articulates edge with quant support | Partial quantitative support for claimed edge | Evidence of style drift vs stated philosophy | — |

**IP-02 Portfolio Construction**
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| Explicit position sizing rules documented | Sizing informal but consistently applied | No documented position sizing or limits | Only aggregate holdings; no construction methodology |
| Concentration limits enforced systematically | Limit breach on ≤2 occasions with remediation | Persistent concentration breaches | — |
| Sector/factor tilts explained within mandate | Minor unexplained tilt; manager provides rationale | Systematic unexplained deviations | — |

**IP-03 Performance Attribution**
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| BHB or factor attribution run monthly | Attribution run quarterly only | No attribution process in place | Attribution reports not provided |
| Attribution in quarterly investor reports | Methodology not independently validated | Performance claimed without attribution | Fund <12 months old |
| Stock selection vs allocation clearly split | Allocation effect only; security-level absent | — | — |

**IP-04 Benchmark Appropriateness**
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| Benchmark reflects investable universe | Broad benchmark; minor mismatch documented | Benchmark inconsistent with construction | No benchmark specified in mandate |
| TE vs benchmark consistent with risk budget | TE elevated; written justification provided | Manager cherry-picks benchmark for flattery | — |

**RO-01 Risk Management Framework** *(VETO)*
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| Independent risk function separate from PM | Risk oversight exists but reports to PM | No independent risk oversight | Risk policy not provided |
| Daily VaR/CVaR with breach escalation | Stress testing annual only | Multiple material limit breaches unresolved | — |
| Quarterly liquidity stress testing | Escalation procedures informal | — | — |

**RO-02 Operational Infrastructure**
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| Tier-1 PAS/OMS; independent custodian | Reconciliation weekly vs daily | No independent custodian | Service provider list not disclosed |
| Daily reconciliation | SOC report >18 months old | Reconciliation failures unresolved >30 days | — |
| SSAE 18 / ISAE 3402 SOC report available | — | — | — |

**RO-03 Key Person Risk**
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| ≥3 senior investment professionals | 2-person team; succession documented; tenure >5yr | Single decision-maker; no succession plan | Org chart not provided |
| Key-person clause in PDS with notification rights | Key-person clause absent; AUM <$100M | Key-person departed <12 months without notification | — |
| Succession plan documented and tested | — | — | — |

**RO-04 Business Continuity**
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| BCP/DR tested annually with documented results | BCP exists; last test >18 months ago | No BCP/DR plan | BCP document not provided |
| RPO ≤4h, RTO ≤8h | RTO >8h but <24h with remediation plan | Critical failure <24 months; no post-mortem | — |

**CE-01 Regulatory Compliance** *(VETO)*
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| AFSL in good standing; no conditions | Minor breach; remediated <90 days; ASIC notified | AFSL suspended, cancelled, or under conditions | AFSL number not provided |
| Compliance framework with annual board sign-off | RG 97 minor non-compliance; corrective PDS issued | Criminal conviction or enforceable undertaking <5yr | — |
| No material ASIC/APRA findings <3 years | — | Material breach unremediated | — |

**CE-02 ESG Integration**
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| Formal ESG policy integrated (not overlay) | ESG considered; formalisation in progress | ESG excluded with no disclosure | ESG policy not provided |
| UNPRI signatory with public disclosure | UNPRI signatory; reporting partial | Greenwashing: ESG claims unsupported | — |
| ESG data provider and scoring documented | — | — | — |

**CE-03 Conflicts of Interest**
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| Conflicts register reviewed by board/compliance | Register exists; reviewed >12 months ago | No conflicts register or policy | FSG / conflicts disclosure not provided |
| Related-party transactions disclosed in PDS | One undisclosed related-party; remediated | Material undisclosed conflict affecting portfolio | — |

**CO-01 Fee Transparency**
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| RG 97 ICR and MER disclosed; all components itemised | Fees disclosed; indirect cost methodology unclear | Fee schedule incomplete; hidden costs identified | Current PDS not provided |
| Perf fee with clear HWM and hurdle | Perf fee hurdle below benchmark return | Fees materially misrepresented vs PDS | — |

**CO-02 Business Viability**
| Pass | Conditional | Fail | Insufficient Evidence |
|------|-------------|------|-----------------------|
| AUM >$100M or parent balance-sheet backing | AUM $50–100M; positive trajectory; 2yr runway | Going-concern qualification in last audit | Financial statements not provided |
| Revenue covers costs; 3-year audited P&L | Single mandate >40% AUM; redemption risk noted | AUM <$50M with negative 12-month trend | — |
| No going-concern qualification | — | — | — |

---

## 3. Evidence Queries

```python
# packages/portfolio_dd/src/wealth_management_portal/portfolio_dd/evidence_queries.py

EVIDENCE_QUERIES: dict[str, list[str]] = {
    "IP-01": [
        "investment philosophy statement alpha generation process {fund_name}",
        "investment mandate constraints style drift policy {fund_name}",
        "portfolio manager interview notes decision-making framework {fund_name}",
        "investment policy statement IPS version history {fund_name}",
    ],
    "IP-02": [
        "position sizing rules concentration limits portfolio construction {fund_name}",
        "sector allocation factor tilt guidelines mandate compliance {fund_name}",
        "portfolio holdings history construction methodology {fund_name}",
        "limit breach log remediation records {fund_name}",
    ],
    "IP-03": [
        "performance attribution report BHB Brinson factor model {fund_name}",
        "quarterly investor letter attribution stock selection allocation effect {fund_name}",
        "attribution methodology documentation independent validation {fund_name}",
        "return decomposition active share benchmark contribution {fund_name}",
    ],
    "IP-04": [
        "benchmark selection rationale investment mandate {fund_name}",
        "tracking error active risk budget benchmark comparison {fund_name}",
        "composite benchmark custom index justification {fund_name}",
    ],
    "RO-01": [
        "risk management framework policy independent risk function {fund_name}",
        "VaR CVaR daily monitoring breach escalation procedure {fund_name}",
        "liquidity stress test scenario analysis results {fund_name}",
        "risk limit breach log remediation risk committee minutes {fund_name}",
    ],
    "RO-02": [
        "custodian arrangement independent reconciliation daily {fund_name}",
        "portfolio accounting system OMS technology infrastructure {fund_name}",
        "SSAE18 ISAE3402 SOC1 SOC2 audit report service organisation {fund_name}",
        "operational incident log reconciliation failures {fund_name}",
    ],
    "RO-03": [
        "investment team organisational chart biographies {fund_name}",
        "key person clause PDS redemption trigger notification {fund_name}",
        "succession plan deputy portfolio manager talent pipeline {fund_name}",
        "staff turnover history senior investment professional departures {fund_name}",
    ],
    "RO-04": [
        "business continuity plan disaster recovery BCP DR {fund_name}",
        "RTO RPO recovery time objective BCP test results {fund_name}",
        "technology outage incident log critical system failure {fund_name}",
    ],
    "CE-01": [
        "AFSL licence conditions Australian Financial Services Licence ASIC register {fund_name}",
        "compliance framework breach log ASIC APRA regulatory action {fund_name}",
        "RG97 fee disclosure product disclosure statement PDS compliance {fund_name}",
        "enforceable undertaking banning order criminal conviction {fund_name}",
    ],
    "CE-02": [
        "ESG policy responsible investment framework integration methodology {fund_name}",
        "UNPRI signatory reporting assessment score {fund_name}",
        "ESG data provider scoring negative screening exclusions {fund_name}",
        "greenwashing ASIC review ESG claim substantiation {fund_name}",
    ],
    "CE-03": [
        "conflicts of interest register related party transactions {fund_name}",
        "financial services guide FSG conflicts disclosure {fund_name}",
        "board compliance review conflicts policy {fund_name}",
    ],
    "CO-01": [
        "management expense ratio MER indirect cost ratio ICR RG97 {fund_name}",
        "performance fee high water mark hurdle rate fee schedule {fund_name}",
        "product disclosure statement PDS fee table current {fund_name}",
    ],
    "CO-02": [
        "assets under management AUM trend growth redemptions {fund_name}",
        "audited financial statements profit loss going concern {fund_name}",
        "revenue operating cost profitability fund manager viability {fund_name}",
        "concentration risk single mandate client AUM percentage {fund_name}",
    ],
}
```

---

## 4. Aggregation Logic

```python
# packages/portfolio_dd/src/wealth_management_portal/portfolio_dd/aggregation.py
from __future__ import annotations
from typing import Literal
from wealth_management_portal.portfolio_dd.models import (
    AssessmentCriterion, CriterionResult, PortfolioDDResult,
    Rating, FRAMEWORK_V1, CRITERION_MAP,
)

RATING_SCORES: dict[Rating, float] = {
    Rating.PASS:                  1.0,
    Rating.CONDITIONAL:           0.5,
    Rating.FAIL:                  0.0,
    Rating.INSUFFICIENT_EVIDENCE: None,  # excluded from weighted avg
}

def compute_weighted_score(results: list[CriterionResult]) -> float | None:
    """Weighted average excluding INSUFFICIENT_EVIDENCE ratings."""
    total_weight = 0.0
    weighted_sum = 0.0
    for r in results:
        score = RATING_SCORES[r.rating]
        if score is None:
            continue
        criterion = CRITERION_MAP[r.criterion_id]
        total_weight += criterion.weight
        weighted_sum += score * criterion.weight
    if total_weight == 0:
        return None
    return round(weighted_sum / total_weight, 4)

def get_veto_triggers(results: list[CriterionResult]) -> list[str]:
    """Return criterion IDs that are veto-eligible and rated FAIL."""
    veto_ids = []
    for r in results:
        criterion = CRITERION_MAP[r.criterion_id]
        if criterion.is_veto and r.rating == Rating.FAIL:
            veto_ids.append(r.criterion_id)
    return veto_ids

def overall_recommendation(
    results: list[CriterionResult],
) -> Literal["approve", "conditional_approve", "reject", "refer_to_committee"]:
    """
    Decision matrix:
      - Any veto FAIL                          → reject
      - Score is None (all insufficient)       → refer_to_committee
      - Score < 0.40                           → reject
      - 0.40 ≤ score < 0.65                   → conditional_approve
      - score ≥ 0.65 with no CONDITIONALs     → approve
      - score ≥ 0.65 with ≥1 CONDITIONAL      → conditional_approve
      - ≥3 INSUFFICIENT_EVIDENCE ratings       → refer_to_committee
    """
    vetos = get_veto_triggers(results)
    if vetos:
        return "reject"

    insufficient_count = sum(1 for r in results if r.rating == Rating.INSUFFICIENT_EVIDENCE)
    if insufficient_count >= 3:
        return "refer_to_committee"

    score = compute_weighted_score(results)
    if score is None:
        return "refer_to_committee"

    if score < 0.40:
        return "reject"

    has_conditional = any(r.rating == Rating.CONDITIONAL for r in results)
    if score >= 0.65 and not has_conditional:
        return "approve"

    return "conditional_approve"

def build_portfolio_dd_result(
    portfolio_id: str,
    results: list[CriterionResult],
    hitl_reasons: list[str],
    assessor_notes: str = "",
) -> PortfolioDDResult:
    veto_triggers = get_veto_triggers(results)
    return PortfolioDDResult(
        portfolio_id=portfolio_id,
        criterion_results=results,
        weighted_score=compute_weighted_score(results),
        overall_recommendation=overall_recommendation(results),
        veto_triggers=veto_triggers,
        hitl_required=bool(hitl_reasons),
        hitl_reasons=hitl_reasons,
        assessor_notes=assessor_notes,
    )
```

---

## 5. HITL Trigger Conditions

| # | Condition | Threshold | Rationale |
|---|-----------|-----------|-----------|
| H-1 | Veto criterion rated FAIL | Any veto FAIL (RO-01, CE-01) | Regulatory or risk failure requires human sign-off before reject |
| H-2 | Weighted score in ambiguous band | 0.40 ≤ score < 0.55 | Marginal pass/fail boundary; automated decision unreliable |
| H-3 | ≥2 INSUFFICIENT_EVIDENCE ratings | count ≥ 2 | Inadequate evidence base; human must request additional docs |
| H-4 | Conflict between agent ratings | CE-01 or CE-03 = CONDITIONAL + CO-02 = CONDITIONAL | Compound regulatory + viability risk exceeds automated authority |
| H-5 | Low evidence confidence | Any criterion evidence_refs = [] (no supporting docs) | Rating made with zero evidence citations |

```python
# packages/portfolio_dd/src/wealth_management_portal/portfolio_dd/hitl.py
from wealth_management_portal.portfolio_dd.models import CriterionResult, Rating, CRITERION_MAP

VETO_IDS = {cid for cid, c in __import__(
    "wealth_management_portal.portfolio_dd.models", fromlist=["CRITERION_MAP"]
).CRITERION_MAP.items() if c.is_veto}

def is_hitl_required(results: list[CriterionResult]) -> tuple[bool, list[str]]:
    """
    Returns (hitl_required, reasons).
    Evaluated in priority order; all matching conditions are collected.
    """
    reasons: list[str] = []
    result_map = {r.criterion_id: r for r in results}

    # H-1: Veto FAIL
    for r in results:
        from wealth_management_portal.portfolio_dd.models import CRITERION_MAP
        if CRITERION_MAP[r.criterion_id].is_veto and r.rating == Rating.FAIL:
            reasons.append(f"H-1: Veto criterion {r.criterion_id} rated FAIL — human sign-off required before reject")

    # H-2: Ambiguous score band
    from wealth_management_portal.portfolio_dd.aggregation import compute_weighted_score
    score = compute_weighted_score(results)
    if score is not None and 0.40 <= score < 0.55:
        reasons.append(f"H-2: Weighted score {score:.3f} in ambiguous band [0.40, 0.55)")

    # H-3: Multiple insufficient evidence
    insufficient = [r.criterion_id for r in results if r.rating == Rating.INSUFFICIENT_EVIDENCE]
    if len(insufficient) >= 2:
        reasons.append(f"H-3: {len(insufficient)} criteria lack sufficient evidence: {insufficient}")

    # H-4: Compound regulatory + viability risk
    compliance_conditional = result_map.get("CE-01", None)
    conflicts_conditional  = result_map.get("CE-03", None)
    viability_conditional  = result_map.get("CO-02", None)
    if (
        compliance_conditional and compliance_conditional.rating == Rating.CONDITIONAL
        and conflicts_conditional and conflicts_conditional.rating == Rating.CONDITIONAL
        and viability_conditional and viability_conditional.rating == Rating.CONDITIONAL
    ):
        reasons.append("H-4: CE-01 + CE-03 + CO-02 all CONDITIONAL — compound risk exceeds automated authority")

    # H-5: Zero evidence citations on any criterion
    no_evidence = [r.criterion_id for r in results if not r.evidence_refs]
    if no_evidence:
        reasons.append(f"H-5: Criteria with no evidence citations: {no_evidence}")

    return bool(reasons), reasons
```

---

## 6. Framework Assessor Prompt Template

```jinja2
{# packages/portfolio_dd/src/wealth_management_portal/portfolio_dd/templates/assessor_prompt.j2 #}
You are the **Framework Assessor** for the Wealth Management Portal Due Diligence Engine.

Your task is to rate a **single DD criterion** for a fund, based solely on the evidence provided.
Do not hallucinate. If the evidence is absent or insufficient to make a determination, say so.

---

## Criterion Under Assessment

| Field        | Value |
|--------------|-------|
| ID           | {{ criterion.id }} |
| Name         | {{ criterion.name }} |
| Category     | {{ criterion.category.value }} |
| Weight       | {{ "%.0f"|format(criterion.weight * 100) }}% |
| Veto-Eligible | {{ "YES — a FAIL here will reject the entire fund" if criterion.is_veto else "No" }} |

---

## Rating Rubric

**PASS** — award if ALL of the following are clearly evidenced:
{% for indicator in criterion.rubric.pass_indicators %}
- {{ indicator }}
{% endfor %}

**CONDITIONAL** — award if evidence is mixed or incomplete:
{% for indicator in criterion.rubric.conditional_indicators %}
- {{ indicator }}
{% endfor %}

**FAIL** — award if ANY of the following are evidenced:
{% for indicator in criterion.rubric.fail_indicators %}
- {{ indicator }}
{% endfor %}

**INSUFFICIENT_EVIDENCE** — award if:
{% for indicator in criterion.rubric.insufficient_indicators %}
- {{ indicator }}
{% endfor %}

---

## Fund Under Review

| Field        | Value |
|--------------|-------|
| Portfolio ID | {{ portfolio_id }} |
| Fund Name    | {{ fund_name }} |
| DD Date      | {{ dd_date }} |

---

## Evidence Provided

{% if evidence_items %}
{% for item in evidence_items %}
### [{{ loop.index }}] {{ item.source_label }}
**Document type:** {{ item.doc_type }}
**Evidence key:** `{{ item.ref_key }}`

```
{{ item.excerpt | truncate(800) }}
```

{% endfor %}
{% else %}
*No evidence documents were retrieved for this criterion.*
{% endif %}

---

## Instructions

1. Review each evidence item against the rubric above.
2. Select exactly one rating: `pass`, `conditional`, `fail`, or `insufficient_evidence`.
3. Write a concise rationale (3–5 sentences) citing specific evidence items by their index number.
4. List the `ref_key` values of all evidence items that directly supported your rating.
5. Flag `hitl_recommended` as `true` if you are less than 70% confident in your rating,
   or if a veto criterion is rated FAIL or CONDITIONAL.

Respond **only** with a JSON object matching this schema — no prose outside the JSON:

```json
{
  "criterion_id": "{{ criterion.id }}",
  "rating": "<pass|conditional|fail|insufficient_evidence>",
  "score": <1.0|0.5|0.0|null>,
  "rationale": "<3-5 sentence explanation citing evidence indices>",
  "evidence_refs": ["<ref_key_1>", "<ref_key_2>"],
  "hitl_recommended": <true|false>,
  "confidence": <0.0-1.0>
}
```

{% if criterion.is_veto %}
**CRITICAL:** This is a veto criterion. If you rate it FAIL you MUST set `hitl_recommended: true`
and confirm in the rationale that the failure is unambiguous and not a data quality issue.
{% endif %}
```
