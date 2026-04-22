import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Query
from pydantic import BaseModel

# Load environment variables from root .env file
root_dir = Path(__file__).parent.parent.parent.parent
env_path = root_dir / ".env"
load_dotenv(dotenv_path=env_path)

# ruff: noqa: E402, I001
from .aum_handler import (  # noqa: E402
    AUMTrendsResponse,
    DashboardSummaryResponse,
    get_aum_trends,
    get_dashboard_summary,
)
from .client_details_handler import (  # noqa: E402
    ClientDetailsResponse,
    get_client_details,
)
from .client_handler import ClientListResponse, get_clients  # noqa: E402
from .client_search_handler import (  # noqa: E402
    ClientSearchRequest,
    ClientSearchResponse,
    search_clients_nl,
)
from .client_segments_handler import (  # noqa: E402
    ClientSegmentsResponse,
    get_client_segments,
)
from .holdings_handler import HoldingsListResponse, get_client_holdings  # noqa: E402
from .init import app, lambda_handler, logger, tracer  # noqa: E402
from .market_themes_handler import MarketThemesResponse, get_market_themes  # noqa: E402
from .portfolio_themes_handler import (  # noqa: E402
    PortfolioThemesResponse,
    get_portfolio_themes as get_portfolio_themes_v2,
)
from .report_handler import ReportStatusResponse, get_client_report  # noqa: E402
from .top_clients_handler import TopClientsResponse, get_top_clients  # noqa: E402
from .transactions_handler import (  # noqa: E402
    TransactionsListResponse,
    get_client_transactions,
)

handler = lambda_handler


class EchoOutput(BaseModel):
    message: str


@app.get("/echo")
@tracer.capture_method
def echo(message: str) -> EchoOutput:
    return EchoOutput(message=f"{message}")


@app.get("/aum-trends")
@tracer.capture_method
def aum_trends(advisor_id: str = "", limit: int = Query(default=12, ge=1, le=100)) -> AUMTrendsResponse:
    """Get AUM trends data from Redshift"""
    return get_aum_trends(advisor_id or None, limit)


@app.get("/dashboard-summary")
@tracer.capture_method
def dashboard_summary() -> DashboardSummaryResponse:
    """Get dashboard summary metrics from Redshift"""
    return get_dashboard_summary()


@app.get("/client-segments")
@tracer.capture_method
def client_segments() -> ClientSegmentsResponse:
    """Get client segment distribution from Redshift"""
    return get_client_segments()


@app.get("/clients")
@tracer.capture_method
def clients(limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)) -> ClientListResponse:
    """Get all clients from Redshift"""
    return get_clients(limit, offset)


@app.get("/top-clients")
@tracer.capture_method
def top_clients() -> TopClientsResponse:
    """Get top 5 clients by AUM"""
    return get_top_clients()


@app.post("/clients/search")
@tracer.capture_method
def client_search(request: ClientSearchRequest) -> ClientSearchResponse:
    """Natural language search for clients"""
    return search_clients_nl(request.query)


@app.get("/clients/{client_id}")
@tracer.capture_method
def client_details(client_id: str) -> ClientDetailsResponse:
    """Get complete client details from Redshift"""
    return get_client_details(client_id)


@app.get("/clients/{client_id}/holdings")
@tracer.capture_method
def client_holdings(
    client_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> HoldingsListResponse:
    """Get holdings for a specific client from Redshift"""
    return get_client_holdings(client_id, limit, offset)


@app.get("/clients/{client_id}/aum")
@tracer.capture_method
def client_aum(client_id: str, months: int = Query(default=12, ge=1, le=120)):
    """Get AUM data for a specific client"""
    from wealth_management_portal_api.aum_handler import get_client_aum

    return get_client_aum(client_id, months)


@app.get("/clients/{client_id}/asset-allocation")
@tracer.capture_method
def client_asset_allocation(client_id: str):
    """Get asset allocation for a specific client"""
    from wealth_management_portal_api.allocation_handler import (
        get_client_asset_allocation,
    )

    return get_client_asset_allocation(client_id)


@app.get("/clients/{client_id}/transactions")
@tracer.capture_method
def client_transactions(
    client_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TransactionsListResponse:
    """Get transactions for a specific client from Redshift"""
    return get_client_transactions(client_id, limit, offset)


@app.get("/clients/{client_id}/themes")
@tracer.capture_method
def client_themes(client_id: str, limit: int = Query(default=15, ge=1, le=50)) -> PortfolioThemesResponse:
    """Get portfolio-specific themes for a client"""
    return get_portfolio_themes_v2(client_id, limit)


@app.get("/market-themes")
@tracer.capture_method
def market_themes(limit: int = Query(default=6, ge=1, le=50)) -> MarketThemesResponse:
    """Get market themes from Redshift via RedshiftClient"""
    return get_market_themes(limit)


@app.get("/market-themes/{theme_id}/articles")
@tracer.capture_method
def theme_articles(theme_id: str):
    """Get articles for a specific theme"""
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

        return {
            "success": True,
            "theme_id": theme_id,
            "article_count": len(articles),
            "articles": [
                {
                    "url": article.url,
                    "title": article.title,
                    "source": article.source,
                    "published_date": (article.published_date.isoformat() if article.published_date else None),
                    "summary": article.summary,
                }
                for article in articles
            ],
        }
    except Exception as e:
        logger.exception("Error in theme_articles")
        return {"success": False, "error": str(e), "theme_id": theme_id, "articles": []}


# --- Client Report ---


@app.get("/clients/{client_id}/report")
@tracer.capture_method
def client_report(client_id: str) -> ReportStatusResponse:
    """Get latest report status and presigned download URL for a client."""
    return get_client_report(client_id)
