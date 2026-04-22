import asyncio
import contextlib
import json as _json
import os
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from sqlalchemy.pool import QueuePool
from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory
from wealth_management_portal_portfolio_data_access.models.market import Article, Theme, ThemeArticleAssociation
from wealth_management_portal_portfolio_data_access.models.report_record import ClientReport
from wealth_management_portal_portfolio_data_access.repositories import (
    ClientReportRepository,
    InteractionRepository,
    ThemeRepository,
    create_simple_repos,
)
from wealth_management_portal_portfolio_data_access.repositories.article_repository import ArticleRepository
from wealth_management_portal_portfolio_data_access.repositories.report_repository import ReportRepository
from wealth_management_portal_portfolio_data_access.repositories.theme_repository import ThemeArticleRepository

from wealth_management_portal_portfolio_data_server.lambda_functions.utils import serialize_value

os.environ["POWERTOOLS_METRICS_NAMESPACE"] = "PortfolioDataGateway"
os.environ["POWERTOOLS_SERVICE_NAME"] = "PortfolioDataGateway"

logger: Logger = Logger()
metrics: Metrics = Metrics()
tracer: Tracer = Tracer()

# Module-level lazy-initialized connection pool
_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = QueuePool(iam_connection_factory(), pool_size=5, max_overflow=10)
    return _pool


@contextlib.contextmanager
def _conn_factory():
    conn = _get_pool().connect()
    try:
        yield conn
    finally:
        conn.close()


def _serialize_dict(data):
    if isinstance(data, dict):
        return {k: _serialize_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_serialize_dict(item) for item in data]
    return serialize_value(data)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _list_clients(event):
    repos = create_simple_repos(_conn_factory)
    return [
        {
            "client_id": c.client_id,
            "client_first_name": c.client_first_name,
            "client_last_name": c.client_last_name,
            "segment": c.segment,
        }
        for c in repos["client"].get()
    ]


async def _get_client_report_data_async(client_id):
    repos = create_simple_repos(_conn_factory)
    report_repo = ClientReportRepository(_conn_factory)

    client = await asyncio.to_thread(repos["client"].get_one, client_id=client_id)
    if not client:
        return {"error": f"Client '{client_id}' not found. Use list_clients to see available clients."}

    interaction_repo = InteractionRepository(_conn_factory)

    (
        restrictions,
        accounts,
        interactions,
        income_expense_records,
        recommended_products,
        themes,
        portfolios,
        holdings_with_securities,
        performance,
        transactions,
    ) = await asyncio.gather(
        asyncio.to_thread(repos["restriction"].get, client_id=client.client_id),
        asyncio.to_thread(repos["account"].get, client_id=client.client_id),
        asyncio.to_thread(interaction_repo.get_recent, client.client_id, 50),
        asyncio.to_thread(repos["income_expense"].get, client_id=client.client_id),
        asyncio.to_thread(repos["recommended_product"].get),
        asyncio.to_thread(repos["theme"].get, client_id=client_id),
        asyncio.to_thread(report_repo.get_portfolios, client.client_id),
        asyncio.to_thread(report_repo.get_holdings_with_securities, client.client_id),
        asyncio.to_thread(report_repo.get_performance, client.client_id),
        asyncio.to_thread(report_repo.get_transactions, client.client_id),
    )

    income_expense = income_expense_records[0] if income_expense_records else None

    return {
        "client": client.model_dump(mode="json"),
        "restrictions": [r.model_dump(mode="json") for r in restrictions],
        "accounts": [a.model_dump(mode="json") for a in accounts],
        "portfolios": [p.model_dump(mode="json") for p in portfolios],
        "holdings_with_securities": _serialize_dict(holdings_with_securities),
        "performance": [p.model_dump(mode="json") for p in performance],
        "transactions": [t.model_dump(mode="json") for t in transactions],
        "interactions": [i.model_dump(mode="json") for i in interactions],
        "income_expense": income_expense.model_dump(mode="json") if income_expense else None,
        "recommended_products": [rp.model_dump(mode="json") for rp in recommended_products],
        "themes": [t.model_dump(mode="json") for t in themes],
    }


def _get_client_report_data(event):
    return asyncio.run(_get_client_report_data_async(event["client_id"]))


def _save_report(event):
    repo = ReportRepository(_conn_factory)
    report = ClientReport(
        report_id=event["report_id"],
        client_id=event["client_id"],
        s3_path=event["s3_path"],
        generated_date=datetime.fromisoformat(event["generated_date"].replace("Z", "+00:00")),
        status=event["status"],
        next_best_action=event.get("next_best_action"),
    )
    repo.save(report)
    return {"ok": True}


def _save_article(event):
    repo = ArticleRepository(_conn_factory)
    published_date = event.get("published_date")
    article = Article(
        content_hash=event["content_hash"],
        url=event["url"],
        title=event["title"],
        content=event["content"],
        summary=event["summary"],
        published_date=datetime.fromisoformat(published_date.replace("Z", "+00:00"))
        if published_date
        else datetime.now(),
        source=event["source"],
        author=event.get("author"),
        file_path=event.get("file_path"),
        created_at=datetime.now(),
    )
    repo.save(article)
    return {"ok": True, "content_hash": event["content_hash"]}


def _get_existing_article_hashes(event):
    repo = ArticleRepository(_conn_factory)
    return {"ok": True, "hashes": list(repo.get_existing_hashes())}


def _get_existing_article_urls(event):
    repo = ArticleRepository(_conn_factory)
    return {"ok": True, "urls": list(repo.get_existing_urls())}


def _get_recent_articles(event):
    repo = ArticleRepository(_conn_factory)
    articles = repo.get_recent(hours=int(event.get("hours", 48)), limit=int(event.get("limit", 100)))
    return {"ok": True, "articles": [a.model_dump(mode="json") for a in articles]}


def _save_theme(event):
    sources = event["sources"]
    score_breakdown = event.get("score_breakdown")
    matched_tickers = event.get("matched_tickers")

    if isinstance(sources, (list, dict)):
        sources = _json.dumps(sources)
    if isinstance(score_breakdown, dict):
        score_breakdown = _json.dumps(score_breakdown)
    if isinstance(matched_tickers, list):
        matched_tickers = _json.dumps(matched_tickers)

    repo = ThemeRepository(_conn_factory)
    now = datetime.now()
    theme = Theme(
        theme_id=event["theme_id"],
        client_id=event["client_id"],
        ticker=event.get("ticker"),
        title=event["title"],
        sentiment=event["sentiment"],
        article_count=int(event["article_count"]),
        sources=sources,
        created_at=now,
        summary=event["summary"],
        updated_at=now,
        score=float(event["score"]),
        rank=int(event["rank"]),
        score_breakdown=score_breakdown,
        generated_at=now,
        relevance_score=float(event["relevance_score"]) if event.get("relevance_score") is not None else None,
        combined_score=float(event["combined_score"]) if event.get("combined_score") is not None else None,
        matched_tickers=matched_tickers,
        relevance_reasoning=event.get("relevance_reasoning"),
    )
    repo.save(theme)
    return {"ok": True, "theme_id": event["theme_id"]}


def _save_theme_article_association(event):
    repo = ThemeArticleRepository(_conn_factory)
    association = ThemeArticleAssociation(
        theme_id=event["theme_id"],
        article_hash=event["article_hash"],
        client_id=event["client_id"],
        created_at=datetime.now(),
    )
    repo.save(association)
    return {"ok": True}


def _get_top_holdings_by_aum(event):
    repo = ThemeRepository(_conn_factory)
    holdings = repo.get_top_holdings_by_aum(client_id=event["client_id"], limit=int(event.get("limit", 5)))
    return {"ok": True, "holdings": holdings}


def _get_active_clients(event):
    repos = create_simple_repos(_conn_factory)
    clients = repos["client"].get(status="Active")
    return {"ok": True, "client_ids": [c.client_id for c in clients]}


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH = {
    "list_clients": _list_clients,
    "get_client_report_data": _get_client_report_data,
    "save_report": _save_report,
    "save_article": _save_article,
    "get_existing_article_hashes": _get_existing_article_hashes,
    "get_existing_article_urls": _get_existing_article_urls,
    "get_recent_articles": _get_recent_articles,
    "save_theme": _save_theme,
    "save_theme_article_association": _save_theme_article_association,
    "get_top_holdings_by_aum": _get_top_holdings_by_aum,
    "get_active_clients": _get_active_clients,
}


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext):
    logger.info("Received event", extra={"event": event})
    metrics.add_metric(name="InvocationCount", unit=MetricUnit.Count, value=1)

    try:
        tool_full_name = context.client_context.custom["bedrockAgentCoreToolName"]
        tool_name = tool_full_name.split("___")[-1]
        logger.info("Dispatching tool", extra={"tool_name": tool_name})

        handler_fn = _DISPATCH.get(tool_name)
        if not handler_fn:
            raise ValueError(f"Unknown tool: {tool_name}")

        result = handler_fn(event)
        metrics.add_metric(name="SuccessCount", unit=MetricUnit.Count, value=1)
        return result

    except Exception as e:
        logger.exception("Tool invocation failed")
        metrics.add_metric(name="ErrorCount", unit=MetricUnit.Count, value=1)
        return {"error": str(e)}
