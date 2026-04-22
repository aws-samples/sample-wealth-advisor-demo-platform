import json
import os

from pydantic import BaseModel
from wealth_management_portal_common_market_events.redshift import RedshiftClient


class ThemeScoreBreakdown(BaseModel):
    article_count_score: float
    source_diversity_score: float
    recency_score: float
    keyword_score: float


class ThemeArticle(BaseModel):
    title: str
    url: str
    source: str
    published_date: str | None = None


class StockHolding(BaseModel):
    ticker: str
    security_name: str
    aum_value: float


class PortfolioTheme(BaseModel):
    rank: int
    theme_id: str
    client_id: str
    ticker: str | None = None  # Stock ticker for per-stock themes
    title: str
    sentiment: str
    score: float
    relevance_score: float
    combined_score: float
    matched_tickers: list[str]
    article_count: int
    sources: list[str]
    summary: str
    relevance_reasoning: str
    articles: list[ThemeArticle] = []
    score_breakdown: ThemeScoreBreakdown | None = None


class StockThemes(BaseModel):
    """Themes grouped by stock"""

    ticker: str
    security_name: str
    aum_value: float
    themes: list[PortfolioTheme]


class PortfolioThemesResponse(BaseModel):
    success: bool
    client_id: str
    portfolio_tickers: list[str] = []
    stock_themes: list[StockThemes] = []  # Grouped by stock
    themes_count: int
    message: str
    is_stale: bool = False
    stale_message: str | None = None


def get_portfolio_themes(client_id: str, limit: int = 15) -> PortfolioThemesResponse:
    """Get portfolio-specific themes from Redshift (query only - no generation), grouped by stock"""
    try:
        # Get config from environment or use defaults
        workgroup = os.environ.get("REDSHIFT_WORKGROUP", "financial-advisor-wg")
        database = os.environ.get("REDSHIFT_DATABASE", "financial-advisor-db")
        region = os.environ.get("AWS_REGION", "us-west-2")

        redshift = RedshiftClient(workgroup=workgroup, database=database, region=region)

        # Try last 48 hours first; fallback to latest available if empty
        is_stale = False
        themes_data = redshift.get_portfolio_themes(client_id=client_id, limit=limit, hours=48)
        if not themes_data:
            themes_data = redshift.get_portfolio_themes(client_id=client_id, limit=limit)
            if themes_data:
                is_stale = True

        # Get top holdings for metadata
        top_holdings = redshift.get_top_holdings_by_aum(client_id, limit=5)
        holdings_map = {h["ticker"]: h for h in top_holdings}

        # Group themes by stock ticker
        themes_by_stock = {}
        all_tickers = set()

        for theme in themes_data:
            ticker = theme.ticker
            if not ticker:
                continue  # Skip themes without ticker (old portfolio-wide themes)

            all_tickers.add(ticker)

            if ticker not in themes_by_stock:
                themes_by_stock[ticker] = []

            # Parse matched_tickers from JSON string
            matched_tickers_list = [ticker]  # Default to current ticker
            if theme.matched_tickers:
                try:
                    matched_tickers_list = json.loads(theme.matched_tickers)
                except (json.JSONDecodeError, TypeError):
                    # If parsing fails, fall back to ticker
                    matched_tickers_list = [ticker]

            portfolio_theme = PortfolioTheme(
                rank=theme.rank or 0,
                theme_id=theme.theme_id,
                client_id=theme.client_id,
                ticker=ticker,
                title=theme.title,
                sentiment=theme.sentiment or "neutral",
                score=theme.score or 0.0,
                relevance_score=theme.relevance_score or 0.0,
                combined_score=theme.combined_score or 0.0,
                matched_tickers=matched_tickers_list,
                article_count=theme.article_count or 0,
                sources=theme.sources or [],
                summary=theme.summary or "",
                relevance_reasoning=theme.relevance_reasoning or "",
                articles=[],  # Articles would need separate query
                score_breakdown=(ThemeScoreBreakdown(**theme.score_breakdown) if theme.score_breakdown else None),
            )
            themes_by_stock[ticker].append(portfolio_theme)

        # Create StockThemes objects
        stock_themes_list = []
        for ticker in sorted(themes_by_stock.keys()):
            holding = holdings_map.get(ticker, {})
            stock_themes_list.append(
                StockThemes(
                    ticker=ticker,
                    security_name=holding.get("security_name", ticker),
                    aum_value=(float(holding.get("aum_value", 0)) if holding.get("aum_value") else 0.0),
                    themes=themes_by_stock[ticker],
                )
            )

        total_themes = sum(len(st.themes) for st in stock_themes_list)

        return PortfolioThemesResponse(
            success=True,
            client_id=client_id,
            portfolio_tickers=list(all_tickers),
            stock_themes=stock_themes_list,
            themes_count=total_themes,
            message=f"Retrieved {total_themes} portfolio themes across {len(stock_themes_list)} stocks for {client_id}",
            is_stale=is_stale,
            stale_message=(
                "Displaying latest available data — theme generation batch has not run recently." if is_stale else None
            ),
        )
    except Exception as e:
        return PortfolioThemesResponse(
            success=False,
            client_id=client_id,
            portfolio_tickers=[],
            stock_themes=[],
            themes_count=0,
            message=f"Error retrieving portfolio themes: {str(e)}",
        )
