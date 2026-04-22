# Repository for theme operations
import logging
from collections.abc import Callable

from wealth_management_portal_portfolio_data_access.models.market import Theme, ThemeArticleAssociation
from wealth_management_portal_portfolio_data_access.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ThemeRepository(BaseRepository[Theme]):
    """Theme repository with save and query operations."""

    def __init__(self, conn_factory: Callable):
        super().__init__(
            conn_factory,
            Theme,
            "public.themes",
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
        )
        self._conn_factory = conn_factory

    def save(self, theme: Theme) -> None:
        """
        Insert a theme record, ignoring duplicate (theme_id, client_id) on re-runs.
        Redshift does not support INSERT ... ON CONFLICT and single-clause MERGE is not
        enabled on this cluster, so we use plain INSERT and swallow duplicate key errors.
        """
        sql = """
            INSERT INTO public.themes (
                theme_id, client_id, ticker, title, sentiment, article_count, sources,
                created_at, summary, updated_at, score, rank, score_breakdown, generated_at,
                relevance_score, combined_score, matched_tickers, relevance_reasoning
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        with self._conn_factory() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        sql,
                        [
                            theme.theme_id,
                            theme.client_id,
                            theme.ticker,
                            theme.title,
                            theme.sentiment,
                            theme.article_count,
                            theme.sources,
                            theme.created_at,
                            theme.summary,
                            theme.updated_at,
                            theme.score,
                            theme.rank,
                            theme.score_breakdown,
                            theme.generated_at,
                            theme.relevance_score,
                            theme.combined_score,
                            theme.matched_tickers,
                            theme.relevance_reasoning,
                        ],
                    )
                conn.commit()
                logger.info(
                    "saved theme theme_id=%s client_id=%s ticker=%s → table=public.themes OK",
                    theme.theme_id,
                    theme.client_id,
                    theme.ticker,
                )
            except Exception as e:
                conn.rollback()
                # Swallow duplicate key violations so re-runs are idempotent
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    logger.info(
                        "save theme theme_id=%s client_id=%s skipped (already exists)",
                        theme.theme_id,
                        theme.client_id,
                    )
                else:
                    logger.warning(
                        "save theme theme_id=%s client_id=%s FAILED: %s",
                        theme.theme_id,
                        theme.client_id,
                        e,
                    )
                    raise

    def get_general_themes(self, limit: int = 10, hours: int = None) -> list[Theme]:
        """Get general market themes.

        Args:
            limit: Maximum number of themes to return
            hours: Optional - only return themes generated in last N hours
        """
        sql = "SELECT * FROM public.themes WHERE client_id = '__GENERAL__'"
        params = []

        if hours:
            sql += " AND generated_at >= NOW() - INTERVAL '%s hours'"
            params.append(hours)

        sql += " ORDER BY rank LIMIT %s"
        params.append(limit)

        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [self._model.model_validate(dict(zip(cols, row, strict=True))) for row in cur.fetchall()]

    def get_portfolio_themes(self, client_id: str, limit: int = 10, hours: int = None) -> list[Theme]:
        """Get portfolio-specific themes for a client.

        Args:
            client_id: Client identifier
            limit: Maximum number of themes to return
            hours: Optional - only return themes generated in last N hours
        """
        sql = "SELECT * FROM public.themes WHERE client_id = %s"
        params = [client_id]

        if hours:
            sql += " AND generated_at >= NOW() - INTERVAL '%s hours'"
            params.append(hours)

        sql += " ORDER BY combined_score DESC LIMIT %s"
        params.append(limit)

        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [self._model.model_validate(dict(zip(cols, row, strict=True))) for row in cur.fetchall()]

    def get_top_holdings_by_aum(self, client_id: str, limit: int = 5) -> list[dict]:
        """Get top holdings by AUM (market_value) for a client."""
        sql = """
            SELECT ticker, security_name, market_value AS aum_value
            FROM public.client_portfolio_holdings
            WHERE client_id = %s
            ORDER BY market_value DESC
            LIMIT %s
        """
        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql, [client_id, limit])
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


class ThemeArticleRepository(BaseRepository[ThemeArticleAssociation]):
    """Repository for theme-article associations."""

    def __init__(self, conn_factory: Callable):
        super().__init__(
            conn_factory,
            ThemeArticleAssociation,
            "public.theme_article_associations",
            {"theme_id", "article_hash", "client_id", "created_at"},
        )
        self._conn_factory = conn_factory

    def save(self, association: ThemeArticleAssociation) -> None:
        """
        Insert a theme-article association, ignoring duplicates on re-runs.
        Plain INSERT — swallows duplicate key errors for idempotency.
        Redshift does not support INSERT ... ON CONFLICT and single-clause MERGE
        is not enabled on this cluster.
        """
        sql = """
            INSERT INTO public.theme_article_associations (theme_id, article_hash, client_id, created_at)
            VALUES (%s, %s, %s, %s)
        """
        with self._conn_factory() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        sql,
                        [
                            association.theme_id,
                            association.article_hash,
                            association.client_id,
                            association.created_at,
                        ],
                    )
                conn.commit()
                logger.info(
                    "saved association theme_id=%s article_hash=%s client_id=%s"
                    " → table=public.theme_article_associations OK",
                    association.theme_id,
                    association.article_hash,
                    association.client_id,
                )
            except Exception as e:
                conn.rollback()
                # Swallow duplicate key violations so re-runs are idempotent
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    logger.info(
                        "save association theme_id=%s article_hash=%s skipped (already exists)",
                        association.theme_id,
                        association.article_hash,
                    )
                else:
                    logger.warning(
                        "save association theme_id=%s article_hash=%s FAILED: %s",
                        association.theme_id,
                        association.article_hash,
                        e,
                    )
                    raise

    def get_articles_for_theme(self, theme_id: str, client_id: str) -> list[str]:
        """Get article hashes for a theme."""
        sql = """
            SELECT article_hash FROM public.theme_article_associations
            WHERE theme_id = %s AND client_id = %s
        """
        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql, [theme_id, client_id])
            return [row[0] for row in cur.fetchall()]
