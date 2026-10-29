# Spec 01: Domain Model & Data Design

## 1. Pydantic Models

```python
# packages/portfolio_dd/wealth_management_portal/portfolio_dd/models.py
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# ── Enumerations ─────────────────────────────────────────────────────────────

class DDCategory(StrEnum):
    INVESTMENT_PROCESS = "investment_process"
    RISK_OPERATIONS    = "risk_operations"
    COMPLIANCE_ESG     = "compliance_esg"
    COMMERCIAL         = "commercial"


class RAGStatus(StrEnum):
    RED    = "red"
    AMBER  = "amber"
    GREEN  = "green"
    GREY   = "grey"   # not yet assessed


class DDStatus(StrEnum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE    = "complete"
    FAILED      = "failed"


class AssetClass(StrEnum):
    AUSTRALIAN_EQUITIES    = "australian_equities"
    GLOBAL_EQUITIES        = "global_equities"
    FIXED_INCOME           = "fixed_income"
    MULTI_ASSET            = "multi_asset"
    ALTERNATIVES           = "alternatives"
    INFRASTRUCTURE         = "infrastructure"


# ── Entity 1: InvestmentManager ───────────────────────────────────────────────

class InvestmentManager(BaseModel):
    manager_id:   str = Field(default_factory=lambda: f"mgr_{uuid4().hex[:8]}")
    name:         str
    afsl_number:  str
    abn:          str
    hq_city:      str
    founded_year: int
    key_person:   str                     # primary portfolio manager
    aum_aud_bn:   float                   # AUM in AUD billions
    website:      str | None = None
    created_at:   datetime = Field(default_factory=datetime.utcnow)


# ── Entity 2: Portfolio ───────────────────────────────────────────────────────

class Portfolio(BaseModel):
    portfolio_id:   str = Field(default_factory=lambda: f"pf_{uuid4().hex[:8]}")
    manager_id:     str
    name:           str
    apir_code:      str                   # APIR identifier, e.g. "AMP0001AU"
    asset_class:    AssetClass
    benchmark:      str                   # e.g. "S&P/ASX 200 TR"
    inception_date: str                   # ISO date "YYYY-MM-DD"
    aum_aud_m:      float                 # AUM in AUD millions
    fee_bps:        int                   # total ongoing charge, basis points
    min_investment: int = 10_000          # AUD
    is_active:      bool = True
    created_at:     datetime = Field(default_factory=datetime.utcnow)


# ── Entity 3: AssessmentCriterion ─────────────────────────────────────────────

class AssessmentCriterion(BaseModel):
    criterion_id:   str
    name:           str
    category:       DDCategory
    weight:         Annotated[float, Field(gt=0, le=1)]
    description:    str
    prompt_hint:    str                   # injected into agent system prompt


# ── Entity 4: DDSession ───────────────────────────────────────────────────────

class DDSession(BaseModel):
    session_id:   str = Field(default_factory=lambda: f"dd_{uuid4().hex[:8]}")
    portfolio_id: str
    framework_id: str = "dd_framework_v1"
    initiated_by: str                     # advisor user_id
    status:       DDStatus = DDStatus.PENDING
    started_at:   datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    s3_report_key: str | None = None


# ── Entity 5: CriterionAssessment ────────────────────────────────────────────

class CriterionAssessment(BaseModel):
    assessment_id:  str = Field(default_factory=lambda: f"ca_{uuid4().hex[:8]}")
    session_id:     str
    criterion_id:   str
    rag_status:     RAGStatus = RAGStatus.GREY
    score:          float | None = None   # 0-10
    summary:        str = ""
    evidence:       list[str] = Field(default_factory=list)   # cited S3 doc keys
    agent_model_id: str = ""
    generated_at:   datetime | None = None


# ── Entity 6: DDReport ────────────────────────────────────────────────────────

class CategorySummary(BaseModel):
    category:     DDCategory
    weight:       float
    weighted_score: float
    rag_status:   RAGStatus


class DDReport(BaseModel):
    report_id:       str = Field(default_factory=lambda: f"rpt_{uuid4().hex[:8]}")
    session_id:      str
    portfolio_id:    str
    framework_id:    str
    overall_score:   float                        # 0-10
    overall_rag:     RAGStatus
    category_summaries: list[CategorySummary]
    assessments:     list[CriterionAssessment]
    recommendation:  str                          # APPROVE / APPROVE_WITH_CONDITIONS / REJECT
    narrative:       str
    generated_at:    datetime = Field(default_factory=datetime.utcnow)
    s3_key:          str = ""


# ── Entity 7: DocumentSource ──────────────────────────────────────────────────

class DocumentSource(BaseModel):
    doc_id:       str = Field(default_factory=lambda: f"doc_{uuid4().hex[:8]}")
    portfolio_id: str
    doc_type:     str                             # "pds", "annual_report", "fsg", "other"
    filename:     str
    s3_key:       str
    page_count:   int | None = None
    ingested_at:  datetime = Field(default_factory=datetime.utcnow)
    kb_indexed:   bool = False
```

---

## 2. S3 Path Conventions

| Path pattern | Description | Concrete example |
|---|---|---|
| `portfolio-dd/raw/{portfolio_id}/{doc_type}/{filename}` | Ingested source docs (PDFs, Word) | `portfolio-dd/raw/pf_a1b2c3d4/pds/amp_growth_pds_2024.pdf` |
| `portfolio-dd/extracted/{portfolio_id}/{doc_id}.json` | Textract / structured JSON output | `portfolio-dd/extracted/pf_a1b2c3d4/doc_f5e6d7c8.json` |
| `portfolio-dd/reports/{portfolio_id}/{session_id}/report.json` | Full DDReport JSON | `portfolio-dd/reports/pf_a1b2c3d4/dd_9a8b7c6d/report.json` |
| `portfolio-dd/reports/{portfolio_id}/{session_id}/report.pdf` | Rendered PDF for advisor | `portfolio-dd/reports/pf_a1b2c3d4/dd_9a8b7c6d/report.pdf` |
| `portfolio-dd/kb-source/{portfolio_id}/{doc_id}/chunks/{n}.txt` | Knowledge Base source chunks | `portfolio-dd/kb-source/pf_a1b2c3d4/doc_f5e6d7c8/chunks/003.txt` |
| `portfolio-dd/frameworks/{framework_id}.json` | Versioned DD framework definitions | `portfolio-dd/frameworks/dd_framework_v1.json` |

---

## 3. Knowledge Base Design

A single Bedrock Knowledge Base (`portfolio-dd-kb`) indexes all portfolio documents. Each chunk carries metadata attributes enabling per-portfolio and per-doc-type filtering — no separate KB per fund is needed. Embedding model: `amazon.titan-embed-text-v2:0`. Chunking: fixed 512 tokens with 50-token overlap. The S3 data source points to `portfolio-dd/kb-source/`.

Metadata fields stored per chunk: `portfolio_id` (string), `doc_type` (string: pds/annual_report/fsg), `doc_id` (string), `ingested_date` (string ISO). During DD agent retrieval, the agent filters by `portfolio_id` (mandatory) and optionally `doc_type` to constrain results to the fund under assessment, preventing cross-portfolio leakage.

```python
# Bedrock KB retrieval filter — passed to RetrieveAndGenerate / Retrieve APIs
def build_kb_filter(portfolio_id: str, doc_type: str | None = None) -> dict:
    must_clauses = [
        {"equals": {"key": "portfolio_id", "value": portfolio_id}}
    ]
    if doc_type:
        must_clauses.append(
            {"equals": {"key": "doc_type", "value": doc_type}}
        )
    if len(must_clauses) == 1:
        return must_clauses[0]
    return {"andAll": must_clauses}

# Usage examples:
# All docs for a fund:
build_kb_filter("pf_a1b2c3d4")
# → {"equals": {"key": "portfolio_id", "value": "pf_a1b2c3d4"}}

# PDS only:
build_kb_filter("pf_a1b2c3d4", "pds")
# → {"andAll": [
#       {"equals": {"key": "portfolio_id", "value": "pf_a1b2c3d4"}},
#       {"equals": {"key": "doc_type", "value": "pds"}}
#    ]}
```

---

## 4. Sample Data

```python
# packages/portfolio_dd/wealth_management_portal/portfolio_dd/seed_data.py

SAMPLE_MANAGERS: list[dict] = [
    {
        "manager_id": "mgr_amp001",
        "name": "AMP Capital Investors",
        "afsl_number": "232030",
        "abn": "59 001 777 591",
        "hq_city": "Sydney",
        "founded_year": 1849,
        "key_person": "Anna Shelley",
        "aum_aud_bn": 58.2,
        "website": "https://www.ampcapital.com",
    },
    {
        "manager_id": "mgr_pendal001",
        "name": "Pendal Group",
        "afsl_number": "228504",
        "abn": "28 126 385 822",
        "hq_city": "Sydney",
        "founded_year": 1980,
        "key_person": "Crispin Murray",
        "aum_aud_bn": 28.4,
        "website": "https://www.pendalgroup.com",
    },
    {
        "manager_id": "mgr_macq001",
        "name": "Macquarie Investment Management",
        "afsl_number": "237492",
        "abn": "66 002 867 003",
        "hq_city": "Sydney",
        "founded_year": 1969,
        "key_person": "Ben Way",
        "aum_aud_bn": 643.0,
        "website": "https://www.macquarie.com/au/en/asset-management",
    },
    {
        "manager_id": "mgr_aef001",
        "name": "Australian Ethical Investment",
        "afsl_number": "229949",
        "abn": "47 003 188 930",
        "hq_city": "Sydney",
        "founded_year": 1986,
        "key_person": "Mark Simons",
        "aum_aud_bn": 10.7,
        "website": "https://www.australianethical.com.au",
    },
    {
        "manager_id": "mgr_hyperion001",
        "name": "Hyperion Asset Management",
        "afsl_number": "238380",
        "abn": "80 080 135 897",
        "hq_city": "Brisbane",
        "founded_year": 1996,
        "key_person": "Mark Arnold",
        "aum_aud_bn": 8.3,
        "website": "https://www.hyperion.com.au",
    },
]

SAMPLE_PORTFOLIOS: list[dict] = [
    {
        "portfolio_id": "pf_amp001",
        "manager_id": "mgr_amp001",
        "name": "AMP Growth Fund",
        "apir_code": "AMP0450AU",
        "asset_class": "multi_asset",
        "benchmark": "CPI + 4.5% p.a.",
        "inception_date": "1998-07-01",
        "aum_aud_m": 2_840.0,
        "fee_bps": 67,
        "min_investment": 1_000,
    },
    {
        "portfolio_id": "pf_pendal001",
        "manager_id": "mgr_pendal001",
        "name": "Pendal Australian Equities",
        "apir_code": "BTA0011AU",
        "asset_class": "australian_equities",
        "benchmark": "S&P/ASX 300 Accumulation Index",
        "inception_date": "1997-04-01",
        "aum_aud_m": 1_150.0,
        "fee_bps": 85,
        "min_investment": 10_000,
    },
    {
        "portfolio_id": "pf_macq001",
        "manager_id": "mgr_macq001",
        "name": "Macquarie Income Fund",
        "apir_code": "MAQ0045AU",
        "asset_class": "fixed_income",
        "benchmark": "Bloomberg AusBond Bank Bill Index",
        "inception_date": "2000-11-30",
        "aum_aud_m": 4_200.0,
        "fee_bps": 28,
        "min_investment": 5_000,
    },
    {
        "portfolio_id": "pf_aef001",
        "manager_id": "mgr_aef001",
        "name": "Australian Ethical Balanced",
        "apir_code": "AEF0003AU",
        "asset_class": "multi_asset",
        "benchmark": "CPI + 3.5% p.a.",
        "inception_date": "2002-01-01",
        "aum_aud_m": 870.0,
        "fee_bps": 79,
        "min_investment": 1_000,
    },
    {
        "portfolio_id": "pf_hyperion001",
        "manager_id": "mgr_hyperion001",
        "name": "Hyperion Australian Growth Companies",
        "apir_code": "WHT8435AU",
        "asset_class": "australian_equities",
        "benchmark": "S&P/ASX All Ordinaries Accumulation Index",
        "inception_date": "1996-08-01",
        "aum_aud_m": 5_100.0,
        "fee_bps": 110,
        "min_investment": 25_000,
    },
]
```

---

## 5. Framework v1.0

| ID | Criterion | Category | Weight |
|---|---|---|---|
| `ip_01` | Investment Philosophy & Process | investment_process | 0.10 |
| `ip_02` | Portfolio Construction | investment_process | 0.08 |
| `ip_03` | Performance Attribution | investment_process | 0.07 |
| `ip_04` | Benchmark Appropriateness | investment_process | 0.05 |
| `ro_01` | Risk Management Framework | risk_operations | 0.10 |
| `ro_02` | Operational Infrastructure | risk_operations | 0.08 |
| `ro_03` | Key Person Risk | risk_operations | 0.07 |
| `ro_04` | Business Continuity | risk_operations | 0.05 |
| `ce_01` | Regulatory Compliance | compliance_esg | 0.12 |
| `ce_02` | ESG Integration | compliance_esg | 0.08 |
| `ce_03` | Conflicts of Interest | compliance_esg | 0.05 |
| `co_01` | Fee Transparency | commercial | 0.08 |
| `co_02` | Business Viability | commercial | 0.07 |

**Total weight: 1.00**

```python
# packages/portfolio_dd/wealth_management_portal/portfolio_dd/framework.py
from wealth_management_portal.portfolio_dd.models import AssessmentCriterion, DDCategory

DD_FRAMEWORK_V1: list[AssessmentCriterion] = [
    AssessmentCriterion(
        criterion_id="ip_01", name="Investment Philosophy & Process",
        category=DDCategory.INVESTMENT_PROCESS, weight=0.10,
        description="Clarity, consistency, and competitive edge of the investment philosophy",
        prompt_hint="Review PDS sections on investment approach, philosophy statement, and any CIO letters",
    ),
    AssessmentCriterion(
        criterion_id="ip_02", name="Portfolio Construction",
        category=DDCategory.INVESTMENT_PROCESS, weight=0.08,
        description="Systematic approach to position sizing, concentration limits, and diversification",
        prompt_hint="Examine portfolio construction rules, concentration limits, and sector exposure policy",
    ),
    AssessmentCriterion(
        criterion_id="ip_03", name="Performance Attribution",
        category=DDCategory.INVESTMENT_PROCESS, weight=0.07,
        description="Quality and transparency of performance attribution reporting",
        prompt_hint="Look for Brinson attribution tables, factor decomposition, and tracking error disclosure",
    ),
    AssessmentCriterion(
        criterion_id="ip_04", name="Benchmark Appropriateness",
        category=DDCategory.INVESTMENT_PROCESS, weight=0.05,
        description="Whether the stated benchmark reflects true investment universe and mandate",
        prompt_hint="Compare benchmark to actual portfolio holdings and stated asset class mandate",
    ),
    AssessmentCriterion(
        criterion_id="ro_01", name="Risk Management Framework",
        category=DDCategory.RISK_OPERATIONS, weight=0.10,
        description="Robustness of risk controls, limits, and governance structures",
        prompt_hint="Identify risk committee structure, VaR/CVaR limits, drawdown triggers, and escalation procedures",
    ),
    AssessmentCriterion(
        criterion_id="ro_02", name="Operational Infrastructure",
        category=DDCategory.RISK_OPERATIONS, weight=0.08,
        description="Quality of middle/back-office systems, custody, and technology stack",
        prompt_hint="Check custodian details, OMS/PMS systems, reconciliation processes, and audit outcomes",
    ),
    AssessmentCriterion(
        criterion_id="ro_03", name="Key Person Risk",
        category=DDCategory.RISK_OPERATIONS, weight=0.07,
        description="Concentration of investment capability in specific individuals",
        prompt_hint="Identify named portfolio managers, succession plans, and team depth indicators",
    ),
    AssessmentCriterion(
        criterion_id="ro_04", name="Business Continuity",
        category=DDCategory.RISK_OPERATIONS, weight=0.05,
        description="BCP/DR capabilities and testing frequency",
        prompt_hint="Look for BCP policy references, RTO/RPO statements, and disaster recovery test evidence",
    ),
    AssessmentCriterion(
        criterion_id="ce_01", name="Regulatory Compliance",
        category=DDCategory.COMPLIANCE_ESG, weight=0.12,
        description="AFSL obligations, ASIC breach history, and internal compliance program",
        prompt_hint="Verify AFSL number, check for disclosed ASIC actions, review compliance framework section",
    ),
    AssessmentCriterion(
        criterion_id="ce_02", name="ESG Integration",
        category=DDCategory.COMPLIANCE_ESG, weight=0.08,
        description="Depth and authenticity of ESG integration in investment process",
        prompt_hint="Look for UNPRI signatory status, exclusion lists, ESG scoring methodology, and stewardship policy",
    ),
    AssessmentCriterion(
        criterion_id="ce_03", name="Conflicts of Interest",
        category=DDCategory.COMPLIANCE_ESG, weight=0.05,
        description="Identification, disclosure, and management of conflicts",
        prompt_hint="Review related-party transaction policy, soft-dollar disclosure, and board independence",
    ),
    AssessmentCriterion(
        criterion_id="co_01", name="Fee Transparency",
        category=DDCategory.COMMERCIAL, weight=0.08,
        description="All-in cost clarity including base fee, performance fee, and transaction costs",
        prompt_hint="Extract MER, ICR, performance fee hurdle, buy/sell spread, and any indirect costs",
    ),
    AssessmentCriterion(
        criterion_id="co_02", name="Business Viability",
        category=DDCategory.COMMERCIAL, weight=0.07,
        description="Manager's financial stability, AUM trajectory, and ownership structure",
        prompt_hint="Look for parent company ownership, AUM growth trend, and staff retention disclosures",
    ),
]

assert abs(sum(c.weight for c in DD_FRAMEWORK_V1) - 1.0) < 1e-9, "Weights must sum to 1.0"
```

---

## 6. Report Output Schema

```json
{
  "report_id": "rpt_c3d4e5f6",
  "session_id": "dd_9a8b7c6d",
  "portfolio_id": "pf_hyperion001",
  "framework_id": "dd_framework_v1",
  "overall_score": 7.4,
  "overall_rag": "green",
  "recommendation": "APPROVE_WITH_CONDITIONS",
  "narrative": "Hyperion Australian Growth Companies demonstrates a well-articulated long-term quality growth philosophy with a 28-year track record. The primary concern is material key person dependency on CIO Mark Arnold and limited succession depth. Fee structure is above peer median but justified by long-run alpha generation. ESG integration is nascent and should be formalised.",
  "category_summaries": [
    { "category": "investment_process", "weight": 0.30, "weighted_score": 2.52, "rag_status": "green" },
    { "category": "risk_operations",    "weight": 0.30, "weighted_score": 1.89, "rag_status": "amber" },
    { "category": "compliance_esg",     "weight": 0.25, "weighted_score": 1.70, "rag_status": "amber" },
    { "category": "commercial",         "weight": 0.15, "weighted_score": 1.29, "rag_status": "green" }
  ],
  "assessments": [
    {
      "assessment_id": "ca_11223344",
      "session_id": "dd_9a8b7c6d",
      "criterion_id": "ip_01",
      "rag_status": "green",
      "score": 9.0,
      "summary": "Philosophy is explicitly documented: quality businesses with sustainable competitive advantages held for 5-10 year periods. Consistent application evidenced by low portfolio turnover (~15% p.a.).",
      "evidence": [
        "portfolio-dd/kb-source/pf_hyperion001/doc_aa11/chunks/002.txt",
        "portfolio-dd/kb-source/pf_hyperion001/doc_aa11/chunks/003.txt"
      ],
      "agent_model_id": "anthropic.claude-sonnet-4-5",
      "generated_at": "2026-07-13T04:22:11Z"
    },
    {
      "assessment_id": "ca_22334455",
      "session_id": "dd_9a8b7c6d",
      "criterion_id": "ro_03",
      "rag_status": "amber",
      "score": 5.0,
      "summary": "Mark Arnold is named as sole decision-maker in PDS. No named successor or deputy PM. Team has grown to 12 but investment authority remains concentrated.",
      "evidence": [
        "portfolio-dd/kb-source/pf_hyperion001/doc_bb22/chunks/007.txt"
      ],
      "agent_model_id": "anthropic.claude-sonnet-4-5",
      "generated_at": "2026-07-13T04:22:45Z"
    },
    {
      "assessment_id": "ca_33445566",
      "session_id": "dd_9a8b7c6d",
      "criterion_id": "ce_01",
      "rag_status": "green",
      "score": 8.5,
      "summary": "AFSL 238380 current and in good standing. No ASIC enforceable undertakings or licence conditions identified. Annual compliance attestation referenced in annual report.",
      "evidence": [
        "portfolio-dd/kb-source/pf_hyperion001/doc_cc33/chunks/001.txt"
      ],
      "agent_model_id": "anthropic.claude-sonnet-4-5",
      "generated_at": "2026-07-13T04:23:01Z"
    },
    {
      "assessment_id": "ca_44556677",
      "session_id": "dd_9a8b7c6d",
      "criterion_id": "co_01",
      "rag_status": "green",
      "score": 8.0,
      "summary": "Management fee 1.10% p.a. (110 bps), no performance fee. Buy/sell spread 0.20%/0.20% disclosed in PDS. ICR matches stated MER with no hidden indirect costs identified.",
      "evidence": [
        "portfolio-dd/kb-source/pf_hyperion001/doc_aa11/chunks/012.txt"
      ],
      "agent_model_id": "anthropic.claude-sonnet-4-5",
      "generated_at": "2026-07-13T04:23:18Z"
    }
  ],
  "generated_at": "2026-07-13T04:24:00Z",
  "s3_key": "portfolio-dd/reports/pf_hyperion001/dd_9a8b7c6d/report.json"
}
```
