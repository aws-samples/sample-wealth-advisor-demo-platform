"""Web search agent tools — financial intelligence web search via Tavily for real-time news and articles."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from strands import tool

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"

# Exposed to main.py for rendering source artifacts in the UI.
last_sources: list[dict[str, Any]] | None = None


TIER_1_DOMAINS = {
    "reuters.com": 1.00,
    "bloomberg.com": 1.00,
    "wsj.com": 0.98,
    "ft.com": 0.98,
    "sec.gov": 1.00,
    "federalreserve.gov": 1.00,
    "finra.org": 0.99,
    "treasury.gov": 0.99,
    "imf.org": 0.97,
    "worldbank.org": 0.97,
}

TIER_2_DOMAINS = {
    "finance.yahoo.com": 0.90,
    "morningstar.com": 0.92,
    "marketwatch.com": 0.88,
    "cnbc.com": 0.87,
    "barrons.com": 0.90,
    "investopedia.com": 0.84,
}

DEFAULT_CREDIBILITY = 0.70


@dataclass
class SearchResult:
    title: str
    url: str
    domain: str
    published_at: str | None
    snippet: str
    provider: str
    query: str
    search_type: str
    relevance_score: float
    freshness_score: float
    credibility_score: float
    composite_score: float


def _get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _parse_iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _freshness_score(published_at: str | None) -> float:
    dt = _parse_iso_date(published_at)
    if not dt:
        return 0.50

    now = datetime.now(UTC)
    age_hours = max((now - dt).total_seconds() / 3600.0, 0.0)

    if age_hours <= 6:
        return 1.00
    if age_hours <= 24:
        return 0.95
    if age_hours <= 72:
        return 0.88
    if age_hours <= 168:
        return 0.78
    if age_hours <= 720:
        return 0.62
    return 0.45


def _credibility_score(domain: str) -> float:
    if domain in TIER_1_DOMAINS:
        return TIER_1_DOMAINS[domain]
    if domain in TIER_2_DOMAINS:
        return TIER_2_DOMAINS[domain]
    return DEFAULT_CREDIBILITY


def _relevance_score(result: dict[str, Any], query: str) -> float:
    title = (result.get("title") or "").lower()
    content = (result.get("content") or "").lower()
    query_terms = [t for t in query.lower().split() if len(t) > 2]

    if not query_terms:
        return 0.50

    hits = 0
    for term in query_terms:
        if term in title:
            hits += 2
        elif term in content:
            hits += 1

    raw = hits / max(len(query_terms) * 2, 1)
    return min(max(raw, 0.35), 1.0)


def _composite_score(relevance: float, freshness: float, credibility: float) -> float:
    # Heavier weight on relevance and credibility for finance workflows.
    return round((0.45 * relevance) + (0.25 * freshness) + (0.30 * credibility), 4)


def _dedupe_key(title: str, domain: str) -> str:
    normalized = "".join(ch.lower() for ch in title if ch.isalnum() or ch.isspace()).strip()
    return f"{domain}|{normalized}"


def _normalize_results(
    raw_results: list[dict[str, Any]],
    query: str,
    search_type: str,
) -> list[SearchResult]:
    normalized: list[SearchResult] = []
    seen: set[str] = set()

    for item in raw_results:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        snippet = (item.get("content") or "").strip()
        published_at = item.get("published_date")
        domain = _get_domain(url)

        if not title or not url:
            continue

        key = _dedupe_key(title, domain)
        if key in seen:
            continue
        seen.add(key)

        relevance = _relevance_score(item, query)
        freshness = _freshness_score(published_at)
        credibility = _credibility_score(domain)
        composite = _composite_score(relevance, freshness, credibility)

        normalized.append(
            SearchResult(
                title=title,
                url=url,
                domain=domain,
                published_at=published_at,
                snippet=snippet[:500],
                provider="tavily",
                query=query,
                search_type=search_type,
                relevance_score=relevance,
                freshness_score=freshness,
                credibility_score=credibility,
                composite_score=composite,
            )
        )

    normalized.sort(key=lambda r: r.composite_score, reverse=True)
    return normalized


def _search_config(search_type: str) -> dict[str, Any]:
    configs = {
        "breaking_news": {"topic": "news", "time_range": "d", "max_results": 8},
        "news": {"topic": "news", "time_range": "w", "max_results": 10},
        "macro": {"topic": "news", "time_range": "w", "max_results": 10},
        "sector": {"topic": "news", "time_range": "w", "max_results": 10},
        "regulatory": {"topic": "general", "time_range": "m", "max_results": 10},
        "company_event": {"topic": "news", "time_range": "w", "max_results": 8},
        "general": {"topic": "general", "time_range": "w", "max_results": 10},
    }
    return configs.get(search_type, configs["general"])


@tool
def web_search(query: str, search_type: str = "general") -> str:
    """
    Retrieve, normalize, rank, and return web evidence for financial analysis.

    This tool is designed for enterprise-grade financial intelligence workflows.
    It does not produce final analysis. It returns normalized evidence for the LLM
    and preserves structured provenance for UI rendering and auditability.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return json.dumps(
            {
                "status": "error",
                "error_type": "configuration_error",
                "message": "TAVILY_API_KEY not configured.",
            },
            ensure_ascii=False,
        )

    cfg = _search_config(search_type)

    payload = {
        "query": query,
        "topic": cfg["topic"],
        "max_results": cfg["max_results"],
        "time_range": cfg["time_range"],
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                TAVILY_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.exception("Tavily timeout for query=%s", query)
        return json.dumps(
            {
                "status": "error",
                "error_type": "timeout",
                "message": "Search timed out while contacting Tavily.",
                "query": query,
                "search_type": search_type,
            },
            ensure_ascii=False,
        )
    except httpx.HTTPStatusError as e:
        logger.exception("Tavily HTTP error for query=%s", query)
        return json.dumps(
            {
                "status": "error",
                "error_type": "http_error",
                "message": f"Tavily returned HTTP {e.response.status_code}.",
                "query": query,
                "search_type": search_type,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        logger.exception("Unexpected Tavily error for query=%s", query)
        return json.dumps(
            {
                "status": "error",
                "error_type": "unexpected_error",
                "message": str(e),
                "query": query,
                "search_type": search_type,
            },
            ensure_ascii=False,
        )

    raw_results = data.get("results", [])
    normalized = _normalize_results(raw_results, query=query, search_type=search_type)

    global last_sources
    last_sources = [
        {
            "title": r.title,
            "url": r.url,
            "date": r.published_at,
            "source": r.domain,
            "provider": r.provider,
            "score": r.composite_score,
        }
        for r in normalized
    ]

    if not normalized:
        return json.dumps(
            {
                "status": "ok",
                "query": query,
                "search_type": search_type,
                "result_count": 0,
                "results": [],
                "note": "No results found.",
            },
            ensure_ascii=False,
        )

    response = {
        "status": "ok",
        "query": query,
        "search_type": search_type,
        "result_count": len(normalized),
        "results": [asdict(r) for r in normalized],
    }
    return json.dumps(response, ensure_ascii=False)
