#!/usr/bin/env python3
"""
Query the theme generation pipeline tables in Redshift.
Requires SSM tunnel to be running on localhost:5439.

Usage:
  cd wealth-management-portal
  uv run python scripts/query-theme-pipeline.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory

connect = iam_connection_factory()


def run_query(conn, label, sql):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        print(f"  rows: {len(rows)}")
        print("  " + " | ".join(f"{c:25s}" for c in cols))
        print("  " + "-" * (28 * len(cols)))
        for row in rows:
            print("  " + " | ".join(f"{str(v)[:25]:25s}" for v in row))


conn = connect()

run_query(conn, "Recent articles (last 48h by created_at)", """
    SELECT source, published_date, created_at, title
    FROM public.articles
    ORDER BY created_at DESC
    LIMIT 20
""")

run_query(conn, "General themes (latest)", """
    SELECT theme_id, title, sentiment, score, rank, article_count, generated_at
    FROM public.themes
    WHERE client_id = '__GENERAL__'
    ORDER BY generated_at DESC, rank ASC
    LIMIT 10
""")

run_query(conn, "All distinct generated_at for __GENERAL__ themes", """
    SELECT generated_at, COUNT(*) as theme_count
    FROM public.themes
    WHERE client_id = '__GENERAL__'
    GROUP BY generated_at
    ORDER BY generated_at DESC
""")

run_query(conn, "Theme-article associations (latest 6 themes)", """
    SELECT ta.theme_id, a.title, a.source
    FROM public.theme_article_associations ta
    JOIN public.articles a ON a.content_hash = ta.article_hash
    WHERE ta.theme_id IN (
        SELECT theme_id FROM public.themes
        WHERE client_id = '__GENERAL__'
        ORDER BY generated_at DESC
        LIMIT 6
    )
    ORDER BY ta.theme_id, a.source
""")

conn.close()
