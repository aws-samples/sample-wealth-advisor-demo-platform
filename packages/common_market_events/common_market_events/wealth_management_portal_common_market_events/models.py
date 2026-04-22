"""Pydantic models for market events data."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Article(BaseModel):
    """Article model matching Redshift schema."""

    content_hash: str = Field(..., description="MD5 hash of article content")
    url: str = Field(..., description="Article URL")
    title: str | None = Field(None, description="Article title")
    content: str | None = Field(None, description="Full article content")
    summary: str | None = Field(None, description="Article summary")
    published_date: datetime | None = Field(None, description="Publication date")
    source: str | None = Field(None, description="Source name (e.g., WSJ, FT)")
    author: str | None = Field(None, description="Article author")
    file_path: str | None = Field(None, description="Local file path")
    created_at: datetime | None = Field(default_factory=datetime.now, description="Record creation timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content_hash": "abc123def456",
                "url": "https://example.com/article",
                "title": "Market Update",
                "source": "Financial Times",
                "published_date": "2026-02-23T10:00:00",
            }
        }
    )


class Theme(BaseModel):
    """Theme model matching Redshift schema."""

    theme_id: str = Field(..., description="Unique theme identifier")
    client_id: str = Field(default="__GENERAL__", description="Client ID or __GENERAL__ for market themes")
    ticker: str | None = Field(None, description="Stock ticker for per-stock themes (e.g., AAPL, GOOGL)")
    title: str = Field(..., description="Theme title")
    sentiment: str | None = Field(None, description="Sentiment: bullish, bearish, neutral")
    article_count: int | None = Field(None, description="Number of articles in theme")
    sources: list[str] | None = Field(None, description="List of source names")
    created_at: datetime | None = Field(None, description="Theme creation timestamp")
    summary: str | None = Field(None, description="Theme summary")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    score: float | None = Field(None, description="Theme score")
    rank: int | None = Field(None, description="Theme ranking")
    score_breakdown: dict[str, Any] | None = Field(None, description="Score breakdown details")
    generated_at: datetime | None = Field(None, description="Generation timestamp")

    # Portfolio-specific fields
    relevance_score: float | None = Field(None, description="Portfolio relevance score")
    combined_score: float | None = Field(None, description="Combined score")
    matched_tickers: list[str] | None = Field(
        None, description="Matched ticker symbols (deprecated - use ticker field)"
    )
    relevance_reasoning: str | None = Field(None, description="Relevance explanation")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "theme_id": "theme_123",
                "client_id": "__GENERAL__",
                "ticker": None,
                "title": "AI Technology Drives Market Optimism",
                "sentiment": "bullish",
                "article_count": 5,
                "score": 85.5,
            }
        }
    )


class ThemeArticleAssociation(BaseModel):
    """Theme-Article association model."""

    theme_id: str = Field(..., description="Theme identifier")
    article_hash: str = Field(..., description="Article content hash")
    client_id: str = Field(default="__GENERAL__", description="Client ID or __GENERAL__")
    created_at: datetime | None = Field(default_factory=datetime.now, description="Association timestamp")


class CrawlLog(BaseModel):
    """Crawl log model."""

    log_id: int | None = Field(None, description="Auto-increment log ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="Crawl timestamp")
    total_crawled: int | None = Field(None, description="Total articles crawled")
    new_articles: int | None = Field(None, description="New articles found")
    duplicates: int | None = Field(None, description="Duplicate articles")
    errors: int | None = Field(None, description="Number of errors")
    sources_stats: dict[str, dict[str, int]] | None = Field(None, description="Per-source statistics")
    created_at: datetime | None = Field(default_factory=datetime.now, description="Record creation timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-02-23T10:00:00",
                "total_crawled": 50,
                "new_articles": 30,
                "duplicates": 15,
                "errors": 5,
                "sources_stats": {"WSJ": {"crawled": 20, "new": 15, "duplicates": 3, "errors": 2}},
            }
        }
    )
