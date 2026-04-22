import os
import time
from typing import Any

from pydantic import BaseModel
from wealth_management_portal_common_market_events.redshift import RedshiftClient

# Simple in-memory cache
_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 300  # 5 minutes


class ThemeScoreBreakdown(BaseModel):
    article_count_score: float
    source_diversity_score: float
    recency_score: float
    keyword_score: float


class MarketTheme(BaseModel):
    rank: int
    theme_id: str
    title: str
    sentiment: str
    score: float
    article_count: int
    sources: list[str]
    summary: str
    score_breakdown: ThemeScoreBreakdown | None = None


class MarketThemesResponse(BaseModel):
    success: bool
    themes_count: int
    themes: list[MarketTheme]
    message: str
    is_stale: bool = False
    stale_message: str | None = None


def get_market_themes(limit: int = 6) -> MarketThemesResponse:
    """Get market themes from RedshiftClient with caching"""
    cache_key = f"market_themes_{limit}"

    # Check cache
    if cache_key in _cache:
        cached_time, cached_response = _cache[cache_key]
        if time.time() - cached_time < CACHE_TTL:
            return cached_response

    try:
        # Get config from environment or use defaults
        workgroup = os.environ.get("REDSHIFT_WORKGROUP", "financial-advisor-wg")
        database = os.environ.get("REDSHIFT_DATABASE", "financial-advisor-db")
        region = os.environ.get("AWS_REGION", "us-west-2")

        client = RedshiftClient(
            workgroup=workgroup,
            database=database,
            region=region,
        )

        # Get general themes from last 48 hours; fallback to latest if empty
        is_stale = False
        themes_list = client.get_general_themes(limit=limit, hours=48)
        if not themes_list:
            themes_list = client.get_general_themes(limit=limit)
            if themes_list:
                is_stale = True

        themes = [
            MarketTheme(
                rank=theme.rank,
                theme_id=theme.theme_id,
                title=theme.title,
                sentiment=theme.sentiment,
                score=theme.score,
                article_count=theme.article_count,
                sources=theme.sources,
                summary=theme.summary,
                score_breakdown=(ThemeScoreBreakdown(**theme.score_breakdown) if theme.score_breakdown else None),
            )
            for theme in themes_list
        ]

        response = MarketThemesResponse(
            success=True,
            themes_count=len(themes),
            themes=themes,
            message=f"Retrieved {len(themes)} market themes",
            is_stale=is_stale,
            stale_message=(
                "Displaying latest available data — theme generation batch has not run recently." if is_stale else None
            ),
        )

        # Cache the response
        _cache[cache_key] = (time.time(), response)

        return response
    except Exception as e:
        return MarketThemesResponse(success=False, themes_count=0, themes=[], message=str(e))


class Article(BaseModel):
    content_hash: str
    title: str
    url: str
    source: str
    published_date: str


class ThemeArticlesResponse(BaseModel):
    success: bool
    theme_id: str
    article_count: int
    articles: list[Article]
    message: str


# Cache for article sources
_articles_cache: dict[str, tuple[float, ThemeArticlesResponse]] = {}


def get_theme_articles(theme_id: str) -> ThemeArticlesResponse:
    """Get articles for a specific theme with caching"""
    cache_key = f"articles_{theme_id}"

    # Check cache
    if cache_key in _articles_cache:
        cached_time, cached_response = _articles_cache[cache_key]
        if time.time() - cached_time < CACHE_TTL:
            return cached_response

    try:
        from wealth_management_portal_common_market_events.redshift import (
            RedshiftClient,
        )

        workgroup = os.environ.get("REDSHIFT_WORKGROUP", "financial-advisor-wg")
        database = os.environ.get("REDSHIFT_DATABASE", "financial-advisor-db")
        region = os.environ.get("AWS_REGION", "us-west-2")

        client = RedshiftClient(
            workgroup=workgroup,
            database=database,
            region=region,
        )

        articles = client.get_theme_articles(theme_id=theme_id)

        response = ThemeArticlesResponse(
            success=True,
            articles=[
                Article(
                    content_hash=a.content_hash,
                    title=a.title,
                    url=a.url,
                    source=a.source,
                    published_date=(
                        a.published_date.isoformat()
                        if hasattr(a.published_date, "isoformat")
                        else str(a.published_date)
                    ),
                )
                for a in articles
            ],
            theme_id=theme_id,
            article_count=len(articles),
            message=f"Retrieved {len(articles)} articles",
        )

        # Cache the response
        _articles_cache[cache_key] = (time.time(), response)

        return response
    except Exception as e:
        return ThemeArticlesResponse(
            success=False,
            theme_id=theme_id,
            article_count=0,
            articles=[],
            message=f"Error retrieving articles: {str(e)}",
        )
