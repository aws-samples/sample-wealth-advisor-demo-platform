"""Data query utilities supporting Athena (S3 Tables) and Redshift Serverless."""

import json
import os
import re
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
    """Client for querying data via Athena or Redshift Serverless."""

    def __init__(
        self,
        workgroup: str,
        database: str,
        region: str = "us-west-2",
    ):
        self.workgroup = workgroup
        self.database = database
        self.region = region
        self._use_athena = os.environ.get("DATA_ENGINE", "athena").lower() == "athena"

        profile = os.environ.get("AWS_PROFILE")
        session = boto3.Session(profile_name=profile, region_name=region)

        if self._use_athena:
            self.client = session.client("athena")
            self._athena_workgroup = os.environ.get("ATHENA_WORKGROUP", "primary")
            self._athena_catalog = os.environ.get("ATHENA_CATALOG", "s3tablescatalog/financial-advisor-s3table")
            self._athena_database = os.environ.get("ATHENA_DATABASE", "financial_advisor")
            self._athena_output = os.environ.get("ATHENA_OUTPUT_LOCATION", "")
        else:
            self.client = session.client("redshift-data")

    def _resolve_params(self, sql: str, parameters: list[dict] | None) -> str:
        """Replace named :param placeholders with literal values for Athena."""
        if not parameters:
            return sql
        for param in sorted(parameters, key=lambda p: len(p["name"]), reverse=True):
            name = param["name"]
            value = param["value"]
            safe_value = re.sub(r"[^\w\s\-._:/+]", "", value)
            if safe_value.isdigit():
                sql = sql.replace(f":{name}", safe_value)
            else:
                sql = sql.replace(f":{name}", f"'{safe_value}'")
        return sql

    def _strip_public_schema(self, sql: str) -> str:
        """Remove 'public.' prefix and fix type/format issues for Athena."""
        sql = sql.replace("public.", "")
        if self._use_athena:
            sql = re.sub(r"(?i)\bAS\s+FLOAT\b", "AS DOUBLE", sql)
            sql = re.sub(r"'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})", r"'\1 \2", sql)
        return sql

    @staticmethod
    def _parse_csv_json_list(value) -> list[str]:
        """Parse a sources-like field that may be CSV-escaped JSON (e.g. '"[""CNBC""')."""
        if value is None:
            return []
        if isinstance(value, list):
            return [s.strip().strip('"') for s in value if s and s.strip().strip('"')]
        if not isinstance(value, str) or not value.strip():
            return []
        cleaned = value.strip().strip('"').replace('""', '"')
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [str(s).strip() for s in parsed if s]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        parts = cleaned.strip("[]").split(",")
        return [p.strip().strip('"').strip("'") for p in parts if p.strip().strip('"')]

    def _qualify_tables(self, sql: str) -> str:
        """Prefix bare table names with fully-qualified catalog.database path."""
        if not self._use_athena:
            return sql
        table_names = [
            "accounts",
            "advisors",
            "articles",
            "client_income_expense",
            "client_investment_restrictions",
            "client_reports",
            "clients",
            "compliance",
            "crawl_log",
            "documents",
            "fees",
            "goals",
            "holdings",
            "interactions",
            "market_data",
            "performance",
            "portfolio_config",
            "portfolios",
            "recommended_products",
            "research",
            "securities",
            "theme_article_associations",
            "themes",
            "transactions",
        ]
        prefix = f'"{self._athena_catalog}"."{self._athena_database}".'
        for table in table_names:
            sql = re.sub(
                rf'(?<![.\w"])(\b{table}\b)(?![.\w])',
                prefix + f'"{table}"',
                sql,
            )
        return sql

    def execute_statement(
        self, sql: str, wait: bool = True, max_attempts: int = 60, parameters: list[dict] | None = None
    ) -> str:
        """Execute SQL statement and optionally wait for completion."""
        if self._use_athena:
            resolved_sql = self._strip_public_schema(self._resolve_params(sql, parameters))
            resolved_sql = self._qualify_tables(resolved_sql)
            start_kwargs: dict = {
                "QueryString": resolved_sql,
                "WorkGroup": self._athena_workgroup,
            }
            if self._athena_output:
                start_kwargs["ResultConfiguration"] = {"OutputLocation": self._athena_output}
            response = self.client.start_query_execution(**start_kwargs)
            query_id = response["QueryExecutionId"]

            if wait:
                for _ in range(max_attempts):
                    status_resp = self.client.get_query_execution(QueryExecutionId=query_id)
                    state = status_resp["QueryExecution"]["Status"]["State"]
                    if state == "SUCCEEDED":
                        break
                    if state == "FAILED":
                        reason = status_resp["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
                        raise Exception(f"Athena query failed: {reason}")
                    if state == "CANCELLED":
                        raise Exception("Athena query was cancelled")
                    time.sleep(0.3)
                else:
                    raise Exception("Athena query timed out")

            return query_id

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
        """Get results from a completed statement."""
        json_fields = {"sources", "score_breakdown", "matched_tickers", "sources_stats"}

        if self._use_athena:
            result = self.client.get_query_results(QueryExecutionId=statement_id)
            result_rows = result.get("ResultSet", {}).get("Rows", [])
            if not result_rows:
                return []
            columns = [col.get("VarCharValue", "") for col in result_rows[0]["Data"]]
            rows = []
            for record in result_rows[1:]:
                row = {}
                for col_name, cell in zip(columns, record["Data"], strict=True):
                    value = cell.get("VarCharValue")
                    if value is None:
                        row[col_name] = None
                    elif col_name in json_fields:
                        try:
                            row[col_name] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            row[col_name] = value
                    else:
                        row[col_name] = value
                rows.append(row)
            return rows

        result = self.client.get_statement_result(Id=statement_id)
        columns = [col["name"] for col in result["ColumnMetadata"]]

        rows = []
        for record in result.get("Records", []):
            row = {}
            for i, col_name in enumerate(columns):
                value = record[i]
                if "stringValue" in value:
                    string_val = value["stringValue"]
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

    def _athena_param_insert(self, sql_named: str, parameters: list[dict]) -> None:
        """Run a named-placeholder INSERT on Athena via ExecutionParameters (safe
        server-side binding — no string interpolation, so commas/quotes/newlines
        in text are preserved). Reuses the existing NULLIF/CAST SQL: each ``:name``
        is replaced with ``?`` in the order it appears and bound to its value.
        ISO timestamps are normalized to Athena's 'YYYY-MM-DD HH:MM:SS' form.
        """
        values_by_name = {p["name"]: p["value"] for p in parameters}
        ordered: list[str] = []

        def _sub(match):
            name = match.group(1)
            val = str(values_by_name.get(name, "__NONE__"))
            ts = re.match(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})", val)
            if ts:
                val = f"{ts.group(1)} {ts.group(2)}"
            # Athena rejects empty-string parameters; fall back to the NULL sentinel.
            ordered.append(val if val != "" else "__NONE__")
            return "?"

        sql_pos = re.sub(r":([a-zA-Z_][a-zA-Z0-9_]*)", _sub, sql_named)
        sql_pos = self._qualify_tables(re.sub(r"(?i)\bAS\s+FLOAT\b", "AS DOUBLE", sql_pos.replace("public.", "")))

        start_kwargs: dict = {
            "QueryString": sql_pos,
            "WorkGroup": self._athena_workgroup,
            "ExecutionParameters": ordered,
        }
        if self._athena_output:
            start_kwargs["ResultConfiguration"] = {"OutputLocation": self._athena_output}
        qid = self.client.start_query_execution(**start_kwargs)["QueryExecutionId"]
        for _ in range(60):
            status = self.client.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
            if status["State"] == "SUCCEEDED":
                return
            if status["State"] in ("FAILED", "CANCELLED"):
                raise Exception(f"Athena parameterized insert failed: {status.get('StateChangeReason', 'Unknown')}")
            time.sleep(0.3)
        raise Exception("Athena parameterized insert timed out")

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
        if self._use_athena:
            self._athena_param_insert(sql, parameters)
        else:
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

    def _latest_themes_sql(self) -> str:
        """Return the inline SQL for latest_themes (view equivalent)."""
        if self._use_athena:
            return """(
                SELECT t.* FROM themes t
                WHERE t.generated_at >= (
                    SELECT max(t2.generated_at) - interval '5' minute
                    FROM themes t2
                    WHERE t2.client_id = t.client_id
                )
            )"""
        return "public.latest_themes"

    def get_general_themes(self, limit: int = 10, hours: int = None) -> list[Theme]:
        """Get general market themes."""
        latest = self._latest_themes_sql()
        sql = f"SELECT * FROM {latest} WHERE client_id = '__GENERAL__'"
        parameters = []

        if hours and self._use_athena:
            from datetime import datetime, timedelta

            cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
            sql += f" AND generated_at >= TIMESTAMP '{cutoff}'"
        elif hours:
            from datetime import datetime, timedelta

            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            sql += " AND generated_at >= :cutoff"
            parameters.append({"name": "cutoff", "value": cutoff})

        sql += f" ORDER BY rank LIMIT {int(limit)}"

        statement_id = self.execute_statement(sql, parameters=parameters or None)
        rows = self.get_statement_result(statement_id)
        for row in rows:
            row["sources"] = self._parse_csv_json_list(row.get("sources"))
            if isinstance(row.get("score_breakdown"), str):
                try:
                    row["score_breakdown"] = json.loads(row["score_breakdown"].replace('""', '"').strip('"'))
                except (json.JSONDecodeError, TypeError, ValueError):
                    row["score_breakdown"] = None
            if isinstance(row.get("matched_tickers"), str):
                try:
                    row["matched_tickers"] = json.loads(row["matched_tickers"].replace('""', '"').strip('"'))
                except (json.JSONDecodeError, TypeError, ValueError):
                    row["matched_tickers"] = None
            if not row.get("score"):
                row["score"] = None
        return [Theme(**row) for row in rows]

    def get_portfolio_themes(
        self, client_id: str, limit: int = 10, hours: int = None, ticker: str = None
    ) -> list[Theme]:
        """Get portfolio-specific themes for a client."""
        latest = self._latest_themes_sql()
        sql = f"SELECT * FROM {latest} WHERE client_id = :client_id"
        parameters = [{"name": "client_id", "value": client_id}]

        if ticker:
            sql += " AND ticker = :ticker"
            parameters.append({"name": "ticker", "value": ticker})

        if hours:
            from datetime import datetime, timedelta

            cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
            sql += " AND generated_at >= TIMESTAMP :cutoff"
            parameters.append({"name": "cutoff", "value": cutoff})

        sql += f" ORDER BY ticker, combined_score DESC LIMIT {int(limit)}"

        statement_id = self.execute_statement(sql, parameters=parameters)
        rows = self.get_statement_result(statement_id)
        return [Theme(**row) for row in rows]

    def get_theme_articles(self, theme_id: str, client_id: str = "__GENERAL__") -> list[Article]:
        """Get articles for a specific theme."""
        if self._use_athena:
            sql = """
            SELECT a.content_hash, a.title, a.url, a.source, CAST(a.published_date AS varchar) AS published_date
            FROM theme_article_associations ta
            JOIN articles a ON ta.article_hash = a.content_hash
            WHERE ta.theme_id = :theme_id
            """
        else:
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
        """Get unique ticker symbols for a client's portfolio holdings."""
        if self._use_athena:
            sql = """
            SELECT DISTINCT s.ticker
            FROM holdings h
            JOIN portfolios pf ON CAST(h.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
            JOIN accounts acc ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
            JOIN securities s ON CAST(h.security_id AS varchar) = CAST(s.security_id AS varchar)
            WHERE CAST(acc.client_id AS varchar) = :client_id
            ORDER BY s.ticker
            """
        else:
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
        if self._use_athena:
            # public.client_portfolio_holdings is a Redshift view that does not
            # exist as an Iceberg table, so on Athena we join the base tables
            # directly (same pattern as get_client_portfolio_tickers). Without
            # this branch the query resolves to schema 'default' and fails with
            # SCHEMA_NOT_FOUND, which crashes the whole portfolio-themes handler.
            sql = f"""
            SELECT
                s.ticker,
                s.security_name,
                SUM(h.quantity * h.current_price) AS aum_value
            FROM holdings h
            JOIN portfolios pf ON CAST(h.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
            JOIN accounts acc ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
            JOIN securities s ON CAST(h.security_id AS varchar) = CAST(s.security_id AS varchar)
            WHERE CAST(acc.client_id AS varchar) = :client_id
            GROUP BY s.ticker, s.security_name
            ORDER BY aum_value DESC
            LIMIT {int(limit)}
            """
        else:
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
