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
    if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
        return _get_client_report_data_athena(event["client_id"])
    return asyncio.run(_get_client_report_data_async(event["client_id"]))


def _get_client_report_data_athena(client_id: str) -> dict:
    """Fetch client report data via Athena (S3 Tables) — no Redshift needed."""
    from wealth_management_portal_portfolio_data_access.repositories.data_api_base_repository import (
        DataApiBaseRepository,
    )

    repo = DataApiBaseRepository()

    client_rows = repo._execute_and_wait(
        "SELECT * FROM clients WHERE client_id = :client_id",
        [{"name": "client_id", "value": client_id}],
    )
    if not client_rows:
        return {"error": f"Client '{client_id}' not found. Use list_clients to see available clients."}

    holdings = repo._execute_and_wait(
        """SELECT h.*, s.security_name, s.asset_class, s.sector, s.currency
           FROM holdings h
           LEFT JOIN securities s ON h.security_id = s.security_id
           WHERE h.client_id = :client_id""",
        [{"name": "client_id", "value": client_id}],
    )

    performance = repo._execute_and_wait(
        "SELECT * FROM performance WHERE client_id = :client_id",
        [{"name": "client_id", "value": client_id}],
    )

    transactions = repo._execute_and_wait(
        "SELECT * FROM transactions WHERE client_id = :client_id ORDER BY transaction_date DESC LIMIT 50",
        [{"name": "client_id", "value": client_id}],
    )

    portfolios = repo._execute_and_wait(
        "SELECT * FROM portfolios WHERE client_id = :client_id",
        [{"name": "client_id", "value": client_id}],
    )

    interactions = repo._execute_and_wait(
        "SELECT * FROM interactions WHERE client_id = :client_id ORDER BY interaction_date DESC LIMIT 50",
        [{"name": "client_id", "value": client_id}],
    )

    themes = repo._execute_and_wait(
        "SELECT * FROM themes WHERE client_id = '__GENERAL__' ORDER BY generated_at DESC LIMIT 6",
        [],
    )

    restrictions = repo._execute_and_wait(
        "SELECT * FROM client_investment_restrictions WHERE client_id = :client_id",
        [{"name": "client_id", "value": client_id}],
    )

    accounts = repo._execute_and_wait(
        "SELECT * FROM accounts WHERE client_id = :client_id",
        [{"name": "client_id", "value": client_id}],
    )

    income_expense = repo._execute_and_wait(
        "SELECT * FROM client_income_expense WHERE client_id = :client_id",
        [{"name": "client_id", "value": client_id}],
    )

    recommended_products = repo._execute_and_wait(
        "SELECT * FROM recommended_products LIMIT 20",
        [],
    )

    return {
        "client": client_rows[0],
        "restrictions": restrictions or [],
        "accounts": accounts or [],
        "portfolios": portfolios or [],
        "holdings_with_securities": holdings or [],
        "performance": performance or [],
        "transactions": transactions or [],
        "interactions": interactions or [],
        "income_expense": income_expense[0] if income_expense else None,
        "recommended_products": recommended_products or [],
        "themes": themes or [],
    }


def _save_report(event):
    if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
        return _save_report_athena(event)
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


def _save_report_athena(event):
    """Save report record via Athena INSERT INTO."""
    from wealth_management_portal_portfolio_data_access.repositories.data_api_base_repository import (
        DataApiBaseRepository,
    )

    repo = DataApiBaseRepository()
    report_id = event["report_id"]
    client_id = event["client_id"]
    s3_path = event.get("s3_path", "")
    status = event.get("status", "complete")
    nba = (event.get("next_best_action") or "").replace("'", "''")[:500]

    sql = f"""
        INSERT INTO client_reports (report_id, client_id, s3_path, status, generated_date, next_best_action)
        VALUES ('{report_id}', '{client_id}', '{s3_path}', '{status}', current_timestamp, '{nba}')
    """
    repo._execute_and_wait(sql)
    return {"ok": True}


def _save_article(event):
    if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
        from wealth_management_portal_portfolio_data_access.repositories.data_api_base_repository import (
            DataApiBaseRepository,
        )

        published_date = event.get("published_date")
        pub = (
            datetime.fromisoformat(published_date.replace("Z", "+00:00")) if published_date else datetime.now()
        ).strftime("%Y-%m-%d %H:%M:%S")
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Athena rejects empty-string ExecutionParameters, so map empty/None to a
        # sentinel and convert back to NULL with NULLIF in the SQL.
        _NULL = "__NULL__"
        DataApiBaseRepository()._execute_parameterized(
            "INSERT INTO articles "
            "(content_hash, url, title, content, summary, published_date, source, author, file_path, created_at) "
            "VALUES (?, ?, ?, ?, NULLIF(?, '__NULL__'), CAST(? AS timestamp), ?, "
            "NULLIF(?, '__NULL__'), NULLIF(?, '__NULL__'), CAST(? AS timestamp))",
            [
                event["content_hash"],
                event["url"],
                event["title"],
                event["content"],
                event.get("summary") or _NULL,
                pub,
                event["source"],
                event.get("author") or _NULL,
                event.get("file_path") or _NULL,
                created,
            ],
        )
        return {"ok": True, "content_hash": event["content_hash"]}

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
    if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
        from wealth_management_portal_portfolio_data_access.repositories.data_api_base_repository import (
            DataApiBaseRepository,
        )

        rows = DataApiBaseRepository()._execute_and_wait("SELECT url FROM articles", [])
        return {"ok": True, "urls": [r["url"] for r in rows if r.get("url")]}
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
