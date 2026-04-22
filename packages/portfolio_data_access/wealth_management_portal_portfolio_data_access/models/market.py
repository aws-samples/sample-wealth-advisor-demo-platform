# Redshift-mirroring models for market themes and articles
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class Theme(BaseModel):
    """Market theme record from Redshift public.themes table."""

    theme_id: str
    client_id: str
    ticker: str | None = None
    title: str
    sentiment: str | None = None
    article_count: int | None = None
    sources: str | None = None
    created_at: datetime | None = None
    summary: str | None = None
    updated_at: datetime | None = None
    score: Decimal | None = None
    rank: int | None = None
    score_breakdown: str | None = None
    generated_at: datetime | None = None
    relevance_score: Decimal | None = None
    combined_score: Decimal | None = None
    matched_tickers: str | None = None
    relevance_reasoning: str | None = None


class Article(BaseModel):
    """Crawled article record from Redshift public.articles table."""

    content_hash: str  # PK
    url: str
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    published_date: datetime | None = None
    source: str | None = None
    author: str | None = None
    file_path: str | None = None
    created_at: datetime | None = None


class ThemeArticleAssociation(BaseModel):
    """Many-to-many join between themes and articles from Redshift public.theme_article_associations."""

    theme_id: str
    article_hash: str
    client_id: str
    created_at: datetime | None = None
