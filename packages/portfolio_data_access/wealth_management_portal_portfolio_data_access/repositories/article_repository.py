# Repository for article operations
from collections.abc import Callable

from wealth_management_portal_portfolio_data_access.models.market import Article
from wealth_management_portal_portfolio_data_access.repositories.base import BaseRepository


class ArticleRepository(BaseRepository[Article]):
    """Article repository with save and query operations."""

    def __init__(self, conn_factory: Callable):
        super().__init__(
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
        )
        self._conn_factory = conn_factory

    def save(self, article: Article) -> None:
        """Insert a new article record."""
        sql = """
            INSERT INTO public.articles (
                content_hash, url, title, content, summary, 
                published_date, source, author, file_path, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    [
                        article.content_hash,
                        article.url,
                        article.title,
                        article.content,
                        article.summary,
                        article.published_date,
                        article.source,
                        article.author,
                        article.file_path,
                        article.created_at,
                    ],
                )
            conn.commit()

    def get_by_hash(self, content_hash: str) -> Article | None:
        """Get article by content hash."""
        return self.get_one(content_hash=content_hash)

    def get_recent(self, hours: int = 48, limit: int = 100) -> list[Article]:
        """Get recent articles within the specified hours, filtered by ingestion time (created_at)."""
        sql = f"""
            SELECT * FROM public.articles 
            WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '{int(hours)} hours'
            ORDER BY created_at DESC
            LIMIT {int(limit)}
        """
        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            return [self._model.model_validate(dict(zip(cols, row, strict=True))) for row in cur.fetchall()]

    def get_existing_hashes(self) -> set[str]:
        """Get all existing article content hashes for duplicate detection."""
        sql = "SELECT content_hash FROM public.articles"
        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql)
            return {row[0] for row in cur.fetchall()}

    def get_existing_urls(self) -> set[str]:
        """Get all existing article URLs for URL-based duplicate detection."""
        sql = "SELECT url FROM public.articles"
        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql)
            return {row[0] for row in cur.fetchall()}
