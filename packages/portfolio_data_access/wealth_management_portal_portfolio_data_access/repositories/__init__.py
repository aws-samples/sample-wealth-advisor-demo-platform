# Repository exports — simple repos as BaseRepository instances, custom repos as classes
from collections.abc import Callable

from wealth_management_portal_portfolio_data_access.models.account import Account
from wealth_management_portal_portfolio_data_access.models.client import Client, ClientRestriction
from wealth_management_portal_portfolio_data_access.models.income_expense import ClientIncomeExpense
from wealth_management_portal_portfolio_data_access.models.market import Article, Theme, ThemeArticleAssociation
from wealth_management_portal_portfolio_data_access.models.portfolio import Holding, PortfolioRecord, Security
from wealth_management_portal_portfolio_data_access.models.recommended_product import RecommendedProduct
from wealth_management_portal_portfolio_data_access.models.transaction import Transaction
from wealth_management_portal_portfolio_data_access.repositories.article_repository import ArticleRepository
from wealth_management_portal_portfolio_data_access.repositories.base import BaseRepository
from wealth_management_portal_portfolio_data_access.repositories.client_report_repository import ClientReportRepository
from wealth_management_portal_portfolio_data_access.repositories.data_api_base_repository import DataApiBaseRepository
from wealth_management_portal_portfolio_data_access.repositories.interaction_repository import InteractionRepository
from wealth_management_portal_portfolio_data_access.repositories.performance_repository import PerformanceRepository
from wealth_management_portal_portfolio_data_access.repositories.portfolio_repository import PortfolioRepository
from wealth_management_portal_portfolio_data_access.repositories.report_repository import ReportRepository
from wealth_management_portal_portfolio_data_access.repositories.theme_repository import (
    ThemeArticleRepository,
    ThemeRepository,
)

__all__ = [
    "BaseRepository",
    "DataApiBaseRepository",
    "ClientReportRepository",
    "PortfolioRepository",
    "PerformanceRepository",
    "InteractionRepository",
    "ReportRepository",
    "ArticleRepository",
    "ThemeRepository",
    "ThemeArticleRepository",
    "Article",
    "Theme",
    "ThemeArticleAssociation",
    "create_simple_repos",
]


def create_simple_repos(conn_factory: Callable) -> dict:
    """Create all simple BaseRepository instances for tables that only need basic CRUD."""
    return {
        "client": BaseRepository(
            conn_factory,
            Client,
            "public.client_search",
            {
                "client_id",
                "client_first_name",
                "client_last_name",
                "client_name",
                "email",
                "phone",
                "address",
                "city",
                "state",
                "zip",
                "date_of_birth",
                "risk_tolerance",
                "investment_objectives",
                "segment",
                "status",
                "advisor_id",
                "client_since",
                "service_model",
                "sophistication",
                "qualified_investor",
            },
        ),
        "restriction": BaseRepository(
            conn_factory,
            ClientRestriction,
            "public.client_restrictions",
            {"restriction_id", "client_id", "restriction", "created_date"},
        ),
        "account": BaseRepository(
            conn_factory,
            Account,
            "public.client_accounts",
            {
                "account_id",
                "client_id",
                "account_type",
                "account_name",
                "opening_date",
                "investment_strategy",
                "status",
                "current_balance",
            },
        ),
        "portfolio": BaseRepository(
            conn_factory,
            PortfolioRecord,
            "public.portfolios",
            {
                "portfolio_id",
                "account_id",
                "portfolio_name",
                "investment_model",
                "target_allocation",
                "benchmark",
                "inception_date",
            },
        ),
        "holding": BaseRepository(
            conn_factory,
            Holding,
            "public.client_portfolio_holdings",
            {
                "position_id",
                "portfolio_id",
                "security_id",
                "quantity",
                "cost_basis",
                "current_price",
                "market_value",
                "unrealized_gain_loss",
                "as_of_date",
            },
        ),
        "security": BaseRepository(
            conn_factory,
            Security,
            "public.securities",
            {
                "security_id",
                "ticker",
                "security_name",
                "security_type",
                "asset_class",
                "sector",
                "current_price",
                "price_date",
            },
        ),
        "income_expense": BaseRepository(
            conn_factory,
            ClientIncomeExpense,
            "public.client_income_expenses",
            {"client_id", "as_of_date", "monthly_income", "monthly_expenses", "sustainability_years"},
        ),
        "recommended_product": BaseRepository(
            conn_factory,
            RecommendedProduct,
            "public.product_catalog",
            {"product_id", "product_name", "product_type", "description", "status", "created_date"},
        ),
        "theme": BaseRepository(
            conn_factory,
            Theme,
            "public.latest_themes",
            {
                "theme_id",
                "client_id",
                "ticker",
                "title",
                "sentiment",
                "article_count",
                "sources",
                "created_at",
                "summary",
                "updated_at",
                "score",
                "rank",
                "score_breakdown",
                "generated_at",
                "relevance_score",
                "combined_score",
                "matched_tickers",
                "relevance_reasoning",
            },
        ),
        "theme_article_association": BaseRepository(
            conn_factory,
            ThemeArticleAssociation,
            "public.theme_article_associations",
            {"theme_id", "article_hash", "client_id", "created_at"},
        ),
        "article": BaseRepository(
            conn_factory,
            Article,
            "public.articles",
            {
                "content_hash",
                "url",
                "title",
                "content",
                "summary",
                "published_date",
                "source",
                "author",
                "file_path",
                "created_at",
            },
        ),
        "transaction": BaseRepository(
            conn_factory,
            Transaction,
            "public.transactions",
            {
                "transaction_id",
                "account_id",
                "security_id",
                "transaction_type",
                "transaction_date",
                "settlement_date",
                "quantity",
                "price",
                "amount",
                "status",
            },
        ),
    }
