"""Synthetic sample data for the 5 demo portfolios."""

from __future__ import annotations

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

# Manager lookup by portfolio_id
MANAGER_BY_PORTFOLIO: dict[str, dict] = {
    p["portfolio_id"]: next(m for m in SAMPLE_MANAGERS if m["manager_id"] == p["manager_id"]) for p in SAMPLE_PORTFOLIOS
}

# Source documents available for each portfolio (simulated KB sources)
SOURCE_DOCUMENTS: dict[str, list[dict]] = {
    "pf_amp001": [
        {
            "name": "AMP Growth Fund - Product Disclosure Statement 2026",
            "key": "source_docs/pf_amp001_pds.pdf",
            "type": "PDS",
            "pages": 24,
        },
        {
            "name": "AMP Growth Fund - Q1 2026 Quarterly Report",
            "key": "source_docs/pf_amp001_quarterly.pdf",
            "type": "Quarterly Report",
            "pages": 8,
        },
        {
            "name": "AMP Capital - Due Diligence Questionnaire Response",
            "key": "source_docs/pf_amp001_ddq.pdf",
            "type": "DDQ",
            "pages": 16,
        },
    ],
    "pf_pendal001": [
        {
            "name": "Pendal Australian Equities - PDS 2026",
            "key": "source_docs/pf_pendal001_pds.pdf",
            "type": "PDS",
            "pages": 20,
        },
        {
            "name": "Pendal Australian Equities - Q1 2026 Performance Report",
            "key": "source_docs/pf_pendal001_quarterly.pdf",
            "type": "Quarterly Report",
            "pages": 6,
        },
        {
            "name": "Pendal Group - Manager DDQ Response",
            "key": "source_docs/pf_pendal001_ddq.pdf",
            "type": "DDQ",
            "pages": 14,
        },
    ],
    "pf_macq001": [
        {
            "name": "Macquarie Income Fund - Product Disclosure Statement",
            "key": "source_docs/pf_macq001_pds.pdf",
            "type": "PDS",
            "pages": 28,
        },
        {
            "name": "Macquarie Income Fund - Q1 2026 Report",
            "key": "source_docs/pf_macq001_quarterly.pdf",
            "type": "Quarterly Report",
            "pages": 10,
        },
    ],
    "pf_aef001": [
        {
            "name": "Australian Ethical Balanced Fund - PDS 2026",
            "key": "source_docs/pf_aef001_pds.pdf",
            "type": "PDS",
            "pages": 22,
        },
        {
            "name": "Australian Ethical - ESG Impact Report 2025",
            "key": "source_docs/pf_aef001_esg.pdf",
            "type": "ESG Report",
            "pages": 12,
        },
        {
            "name": "Australian Ethical - DDQ Response",
            "key": "source_docs/pf_aef001_ddq.pdf",
            "type": "DDQ",
            "pages": 18,
        },
    ],
    "pf_hyperion001": [
        {
            "name": "Hyperion Australian Growth Companies - PDS",
            "key": "source_docs/pf_hyperion001_pds.pdf",
            "type": "PDS",
            "pages": 18,
        },
        {
            "name": "Hyperion - Q1 2026 Investment Letter",
            "key": "source_docs/pf_hyperion001_quarterly.pdf",
            "type": "Quarterly Report",
            "pages": 4,
        },
        {
            "name": "Hyperion Asset Management - DDQ Response",
            "key": "source_docs/pf_hyperion001_ddq.pdf",
            "type": "DDQ",
            "pages": 20,
        },
    ],
}
