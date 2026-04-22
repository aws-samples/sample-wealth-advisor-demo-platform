"""Redshift connection and query utilities."""

import json
import os
import time
from datetime import datetime
from typing import Any

import boto3

from wealth_management_portal_common_market_events.models import (
    Article,
    CrawlLog,
    Theme,
    ThemeArticleAssociation,
)


class RedshiftClient:
    """Client for interacting with Redshift Serverless."""

    def __init__(
        self,
        workgroup: str,
        database: str,
        region: str = "us-west-2",
    ):
        """
        Initialize Redshift client.

        Args:
            workgroup: Redshift Serverless workgroup name
            database: Database name
            region: AWS region
        """
        self.workgroup = workgroup
        self.database = database
        self.region = region

        profile = os.environ.get("AWS_PROFILE")
        session = boto3.Session(profile_name=profile, region_name=region)
        self.client = session.client("redshift-data")

    def execute_statement(
        self, sql: str, wait: bool = True, max_attempts: int = 60, parameters: list[dict] | None = None
    ) -> str:
        """
        Execute SQL statement and optionally wait for completion.

        Args:
            sql: SQL statement to execute
            wait: Whether to wait for completion
            max_attempts: Maximum polling attempts
            parameters: Optional list of named parameters [{"name": "x", "value": "y"}]

        Returns:
            Statement ID
        """
        kwargs = {"WorkgroupName": self.workgroup, "Database": self.database, "Sql": sql}
        if parameters:
            kwargs["Parameters"] = parameters
        response = self.client.execute_statement(**kwargs)
        statement_id = response["Id"]

        if wait:
            attempt = 0
            while attempt < max_attempts:
                status_response = self.client.describe_statement(Id=statement_id)
                status = status_response["Status"]

                if status == "FINISHED":
                    break
                elif status == "FAILED":
                    error_msg = status_response.get("Error", "Unknown error")
                    raise Exception(f"SQL execution failed: {error_msg}")
                elif status == "ABORTED":
                    raise Exception("SQL execution was aborted")

                time.sleep(1)
                attempt += 1

            if attempt >= max_attempts:
                raise Exception("SQL execution timed out")

        return statement_id

    def get_statement_result(self, statement_id: str) -> list[dict[str, Any]]:
        """
        Get results from a completed statement.

        Args:
            statement_id: Statement ID

        Returns:
            List of result rows as dictionaries
        """
        result = self.client.get_statement_result(Id=statement_id)

        # Extract column names
        columns = [col["name"] for col in result["ColumnMetadata"]]

        # JSON fields that need parsing
        json_fields = {"sources", "score_breakdown", "matched_tickers", "sources_stats"}

        # Convert rows to dictionaries
        rows = []
        for record in result.get("Records", []):
            row = {}
            for i, col_name in enumerate(columns):
                # Handle different value types
                value = record[i]
                if "stringValue" in value:
                    string_val = value["stringValue"]
                    # Parse JSON fields
                    if col_name in json_fields and string_val:
                        try:
                            row[col_name] = json.loads(string_val)
                        except json.JSONDecodeError:
                            row[col_name] = string_val
                    else:
                        row[col_name] = string_val
                elif "longValue" in value:
                    row[col_name] = value["longValue"]
                elif "doubleValue" in value:
                    row[col_name] = value["doubleValue"]
                elif "booleanValue" in value:
                    row[col_name] = value["booleanValue"]
                elif "isNull" in value and value["isNull"]:
                    row[col_name] = None
                else:
                    row[col_name] = None
            rows.append(row)

        return rows

    @staticmethod
    def _param(name: str, value: str | None) -> dict:
        """Build a named parameter, using a sentinel for empty/None values."""
        return {"name": name, "value": value if value else "__NONE__"}

    def insert_article(self, article: Article) -> None:
        """Insert an article into Redshift."""
        sql = """
        INSERT INTO articles (
            content_hash, url, title, content, summary,
            published_date, source, author, file_path, created_at
        ) VALUES (
            :content_hash, :url, NULLIF(:title, '__NONE__'),
            NULLIF(:content, '__NONE__'), NULLIF(:summary, '__NONE__'),
            CAST(NULLIF(:published_date, '__NONE__') AS TIMESTAMP),
            NULLIF(:source, '__NONE__'), NULLIF(:author, '__NONE__'),
            NULLIF(:file_path, '__NONE__'), CAST(:created_at AS TIMESTAMP)
        )
        """
        p = self._param
        now = datetime.now().isoformat()
        parameters = [
            p("content_hash", article.content_hash),
            p("url", article.url),
            p("title", article.title),
            p("content", article.content[:65000] if article.content else None),
            p("summary", article.summary),
            p("published_date", article.published_date.isoformat() if article.published_date else None),
            p("source", article.source),
            p("author", article.author),
            p("file_path", article.file_path),
            p("created_at", article.created_at.isoformat() if article.created_at else now),
        ]
        self.execute_statement(sql, parameters=parameters)

    def insert_theme(self, theme: Theme) -> None:
        """Insert a theme into Redshift."""
        now = datetime.now().isoformat()
        sql = """
        INSERT INTO themes (
            theme_id, client_id, ticker, title, sentiment, article_count,
            sources, created_at, summary, updated_at, score, rank,
            score_breakdown, generated_at, relevance_score, combined_score,
            matched_tickers, relevance_reasoning
        ) VALUES (
            :theme_id, :client_id, NULLIF(:ticker, '__NONE__'), :title, NULLIF(:sentiment, '__NONE__'),
            CAST(:article_count AS INTEGER),
            :sources, CAST(:created_at AS TIMESTAMP), NULLIF(:summary, '__NONE__'), CAST(:updated_at AS TIMESTAMP),
            CAST(:score AS FLOAT), CAST(:rank AS INTEGER),
            :score_breakdown, CAST(:generated_at AS TIMESTAMP),
            CAST(NULLIF(:relevance_score, '__NONE__') AS FLOAT),
            CAST(NULLIF(:combined_score, '__NONE__') AS FLOAT),
            :matched_tickers, NULLIF(:relevance_reasoning, '__NONE__')
        )
        """
        p = self._param
        parameters = [
            p("theme_id", theme.theme_id),
            p("client_id", theme.client_id),
            p("ticker", theme.ticker),
            p("title", theme.title),
            p("sentiment", theme.sentiment),
            {"name": "article_count", "value": str(theme.article_count or 0)},
            {"name": "sources", "value": json.dumps(theme.sources) if theme.sources else "[]"},
            {"name": "created_at", "value": theme.created_at.isoformat() if theme.created_at else now},
            p("summary", theme.summary),
            {"name": "updated_at", "value": theme.updated_at.isoformat() if theme.updated_at else now},
            {"name": "score", "value": str(theme.score or 0)},
            {"name": "rank", "value": str(theme.rank or 0)},
            {"name": "score_breakdown", "value": json.dumps(theme.score_breakdown) if theme.score_breakdown else "{}"},
            {"name": "generated_at", "value": theme.generated_at.isoformat() if theme.generated_at else now},
            p("relevance_score", str(theme.relevance_score) if theme.relevance_score else None),
            p("combined_score", str(theme.combined_score) if theme.combined_score else None),
            {"name": "matched_tickers", "value": json.dumps(theme.matched_tickers) if theme.matched_tickers else "[]"},
            p("relevance_reasoning", theme.relevance_reasoning),
        ]
        self.execute_statement(sql, parameters=parameters)

    def insert_theme_article_association(self, association: ThemeArticleAssociation) -> None:
        """Insert a theme-article association."""
        sql = """
        INSERT INTO theme_article_associations (
            theme_id, article_hash, client_id, created_at
        ) VALUES (
            :theme_id, :article_hash, :client_id, CAST(:created_at AS TIMESTAMP)
        )
        """
        parameters = [
            {"name": "theme_id", "value": association.theme_id},
            {"name": "article_hash", "value": association.article_hash},
            {"name": "client_id", "value": association.client_id},
            {
                "name": "created_at",
                "value": association.created_at.isoformat() if association.created_at else datetime.now().isoformat(),
            },
        ]
        self.execute_statement(sql, parameters=parameters)

    def insert_crawl_log(self, log: CrawlLog) -> None:
        """Insert a crawl log entry."""
        sql = """
        INSERT INTO crawl_log (
            timestamp, total_crawled, new_articles, duplicates, errors, sources_stats, created_at
        ) VALUES (
            CAST(:timestamp AS TIMESTAMP), CAST(:total_crawled AS INTEGER), CAST(:new_articles AS INTEGER),
            CAST(:duplicates AS INTEGER), CAST(:errors AS INTEGER), :sources_stats, CAST(:created_at AS TIMESTAMP)
        )
        """
        parameters = [
            {"name": "timestamp", "value": log.timestamp.isoformat()},
            {"name": "total_crawled", "value": str(log.total_crawled or 0)},
            {"name": "new_articles", "value": str(log.new_articles or 0)},
            {"name": "duplicates", "value": str(log.duplicates or 0)},
            {"name": "errors", "value": str(log.errors or 0)},
            {"name": "sources_stats", "value": json.dumps(log.sources_stats) if log.sources_stats else "{}"},
            {
                "name": "created_at",
                "value": log.created_at.isoformat() if log.created_at else datetime.now().isoformat(),
            },
        ]
        self.execute_statement(sql, parameters=parameters)

    def get_articles(self, limit: int = 100, offset: int = 0) -> list[Article]:
        """Get articles from Redshift."""
        sql = f"SELECT * FROM articles ORDER BY published_date DESC LIMIT {limit} OFFSET {offset}"
        statement_id = self.execute_statement(sql)
        rows = self.get_statement_result(statement_id)
        return [Article(**row) for row in rows]

    def get_general_themes(self, limit: int = 10, hours: int = None) -> list[Theme]:
        """
        Get general market themes from Redshift via latest_themes view.

        Args:
            limit: Maximum number of themes to return
            hours: Optional - only return themes generated in last N hours

        Returns:
            List of Theme objects ordered by rank
        """
        sql = "SELECT * FROM public.latest_themes WHERE client_id = '__GENERAL__'"
        parameters = []

        if hours:
            from datetime import datetime, timedelta

            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            sql += " AND generated_at >= :cutoff"
            parameters.append({"name": "cutoff", "value": cutoff})

        sql += f" ORDER BY rank LIMIT {int(limit)}"

        statement_id = self.execute_statement(sql, parameters=parameters or None)
        rows = self.get_statement_result(statement_id)
        for row in rows:
            if isinstance(row.get("sources"), str):
                row["sources"] = json.loads(row["sources"])
            if isinstance(row.get("score_breakdown"), str):
                row["score_breakdown"] = json.loads(row["score_breakdown"])
            if isinstance(row.get("matched_tickers"), str):
                row["matched_tickers"] = json.loads(row["matched_tickers"])
        return [Theme(**row) for row in rows]

    def get_portfolio_themes(
        self, client_id: str, limit: int = 10, hours: int = None, ticker: str = None
    ) -> list[Theme]:
        """
        Get portfolio-specific themes for a client via latest_themes view.

        Args:
            client_id: Client identifier
            limit: Maximum number of themes to return
            hours: Optional - only return themes generated in last N hours
            ticker: Optional - filter themes for specific stock ticker

        Returns:
            List of Theme objects ordered by combined_score
        """
        sql = "SELECT * FROM public.latest_themes WHERE client_id = :client_id"
        parameters = [{"name": "client_id", "value": client_id}]

        if ticker:
            sql += " AND ticker = :ticker"
            parameters.append({"name": "ticker", "value": ticker})

        if hours:
            from datetime import datetime, timedelta

            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            sql += " AND generated_at >= :cutoff"
            parameters.append({"name": "cutoff", "value": cutoff})

        sql += f" ORDER BY ticker, combined_score DESC LIMIT {int(limit)}"

        statement_id = self.execute_statement(sql, parameters=parameters)
        rows = self.get_statement_result(statement_id)
        return [Theme(**row) for row in rows]

    def get_theme_articles(self, theme_id: str, client_id: str = "__GENERAL__") -> list[Article]:
        """Get articles for a specific theme via theme_articles view."""
        sql = """
        SELECT content_hash, title, url, source, published_date
        FROM public.theme_articles
        WHERE theme_id = :theme_id
        """
        parameters = [{"name": "theme_id", "value": theme_id}]
        statement_id = self.execute_statement(sql, parameters=parameters)
        rows = self.get_statement_result(statement_id)
        return [Article(**row) for row in rows]

    def get_client_portfolio_tickers(self, client_id: str) -> list[str]:
        """
        Get unique ticker symbols for a client's portfolio holdings.

        Args:
            client_id: Client identifier

        Returns:
            List of unique ticker symbols
        """
        sql = """
        SELECT DISTINCT ticker
        FROM public.client_portfolio_holdings
        WHERE client_id = :client_id
        ORDER BY ticker
        """
        parameters = [{"name": "client_id", "value": client_id}]
        statement_id = self.execute_statement(sql, parameters=parameters)
        rows = self.get_statement_result(statement_id)
        return [row["ticker"] for row in rows]

    def get_top_holdings_by_aum(self, client_id: str, limit: int = 5) -> list[dict]:
        """
        Get top N holdings by AUM value for a client.

        Args:
            client_id: Client identifier
            limit: Number of top holdings to return (default: 5)

        Returns:
            List of dicts with ticker, security_name, and aum_value
        """
        sql = f"""
        SELECT 
            ticker,
            security_name,
            SUM(quantity * current_price) as aum_value
        FROM public.client_portfolio_holdings
        WHERE client_id = :client_id
        GROUP BY ticker, security_name
        ORDER BY aum_value DESC
        LIMIT {int(limit)}
        """
        parameters = [{"name": "client_id", "value": client_id}]
        statement_id = self.execute_statement(sql, parameters=parameters)
        rows = self.get_statement_result(statement_id)
        return rows
