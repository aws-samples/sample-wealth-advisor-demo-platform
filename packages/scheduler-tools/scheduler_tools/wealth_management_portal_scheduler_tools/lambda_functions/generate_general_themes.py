"""
Lambda handler for generating general market themes.

Runs ThemeProcessor directly (using RedshiftClient for Athena data access)
instead of delegating to the WebCrawlerMcp AgentCore runtime, which has a 180s
sandbox timeout too short for web crawl + LLM generation.
"""

import json
import os
import traceback
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from wealth_management_portal_common_market_events.redshift import RedshiftClient

logger = Logger()
tracer = Tracer()


def _crawl_articles_via_mcp(mcp_arn: str) -> dict:
    """Invoke WebCrawlerMcp to crawl fresh articles (best-effort, timeout tolerant)."""
    from common_auth import SigV4HTTPXAuth
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp.mcp_client import MCPClient

    region = os.environ.get("AWS_REGION", "us-west-2")
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    encoded = mcp_arn.replace(":", "%3A").replace("/", "%2F")
    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded}/invocations?qualifier=DEFAULT"
    mcp_client = MCPClient(
        lambda: streamablehttp_client(url, auth=SigV4HTTPXAuth(creds, region), timeout=170, terminate_on_close=False)
    )
    # Cap the number of sources crawled per run. Each article is persisted via a
    # separate Athena INSERT (seconds each), so an uncapped crawl against a stale
    # table produces hundreds of new articles and blows the Lambda timeout. Capping
    # keeps each run inside the 900s budget; dedup means daily runs still accumulate
    # coverage. THEME_CRAWL_MAX_SOURCES=0/unset means uncapped.
    args: dict = {"rss_only": True}
    _max_sources = os.environ.get("THEME_CRAWL_MAX_SOURCES", "")
    if _max_sources.isdigit() and int(_max_sources) > 0:
        args["max_sources"] = int(_max_sources)
    try:
        with mcp_client as client:
            result = client.call_tool_sync("save_articles", "save_articles_to_redshift", args)
        return json.loads(result["content"][0]["text"])
    except Exception as e:
        return {"success": False, "error": str(e)}


def _generate_themes_locally(hours: int, limit: int) -> dict:
    """Generate themes using RedshiftClient + Bedrock directly in-Lambda."""
    from botocore.config import Config as BotoConfig
    from wealth_management_portal_common_market_events.models import Theme, ThemeArticleAssociation

    workgroup = os.environ.get("REDSHIFT_WORKGROUP", "financial-advisor-wg")
    database = os.environ.get("REDSHIFT_DATABASE", "financial-advisor-db")
    region = os.environ.get("AWS_REGION", "us-west-2")
    raw_model_id = os.environ.get("THEME_BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-5")
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    if "." in raw_model_id and not raw_model_id.startswith("arn:"):
        model_id = f"arn:aws:bedrock:{region}:{account_id}:inference-profile/{raw_model_id}"
    else:
        model_id = raw_model_id

    client = RedshiftClient(workgroup=workgroup, database=database, region=region)

    # 1. Get recent articles
    from datetime import timedelta

    cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    if client._use_athena:
        sql = f"""
            SELECT content_hash, title, url, source, summary,
                   CAST(published_date AS varchar) AS published_date
            FROM articles
            WHERE published_date >= TIMESTAMP '{cutoff}'
            ORDER BY published_date DESC
            LIMIT 200
        """
    else:
        sql = f"""
            SELECT content_hash, title, url, source, summary, published_date
            FROM public.articles
            WHERE published_date >= '{cutoff}'
            ORDER BY published_date DESC
            LIMIT 200
        """
    stmt_id = client.execute_statement(sql)
    rows = client.get_statement_result(stmt_id)
    logger.info("Found %d recent articles (last %d hours)", len(rows), hours)

    if not rows:
        logger.info("No recent articles, falling back to latest available")
        if client._use_athena:
            fallback_sql = """
                SELECT content_hash, title, url, source, summary,
                       CAST(published_date AS varchar) AS published_date
                FROM articles
                ORDER BY published_date DESC
                LIMIT 200
            """
        else:
            fallback_sql = """
                SELECT content_hash, title, url, source, summary, published_date
                FROM public.articles
                ORDER BY published_date DESC
                LIMIT 200
            """
        stmt_id = client.execute_statement(fallback_sql)
        rows = client.get_statement_result(stmt_id)
        logger.info("Fallback found %d articles", len(rows))
        if not rows:
            return {"success": True, "themes_generated": 0, "message": "No articles found"}

    # 2. Call Bedrock to identify themes
    articles_text = ""
    for i, row in enumerate(rows[:100], 1):
        articles_text += f"{i}. {row.get('title', '')}\n"
        articles_text += f"   Source: {row.get('source', '')}\n"
        summary = row.get("summary", "") or ""
        articles_text += f"   Summary: {summary[:200]}...\n\n"

    prompt = f"""Analyze these US market news articles and identify 5-6 major themes or hot topics.

Requirements:
- Each theme must be supported by at least 3 articles
- Focus on actionable market-moving themes
- Provide clear, concise titles
- Rate sentiment as: bullish, bearish, or neutral

Articles:
{articles_text}

Return JSON array:
[{{"title": "...", "sentiment": "bullish|bearish|neutral", "summary": "...", "article_indices": [1,2,3...]}}]"""

    bedrock = boto3.client("bedrock-runtime", config=BotoConfig(region_name=region, retries={"max_attempts": 3}))
    response = bedrock.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 8192},
    )
    blocks = response["output"]["message"]["content"]
    stop_reason = response.get("stopReason")
    # Concatenate all text blocks. Reasoning-capable models (e.g. claude-sonnet-5)
    # emit a reasoningContent block (no "text") before the answer, and can exhaust
    # the token budget on reasoning before producing any answer text. Joining the
    # text blocks tolerates the reasoning block; an empty result means the answer
    # was never emitted (usually stopReason=max_tokens) — log loudly rather than
    # silently generating 0 themes.
    content = "".join(b["text"] for b in blocks if isinstance(b, dict) and "text" in b)
    if not content:
        logger.error(
            "Theme model returned no answer text (stopReason=%s) — a reasoning model may be "
            "exhausting maxTokens before answering. Use a non-reasoning model or raise maxTokens.",
            stop_reason,
        )

    # Parse themes from response
    try:
        start = content.find("[")
        end = content.rfind("]") + 1
        themes_data = json.loads(content[start:end]) if start >= 0 else []
    except (json.JSONDecodeError, ValueError):
        themes_data = []

    if themes_data:
        logger.info("Bedrock identified %d themes", len(themes_data))
    else:
        logger.error(
            "Bedrock identified 0 themes (stopReason=%s, answer_text_len=%d) — themes will not refresh",
            stop_reason,
            len(content),
        )

    # 3. Score, rank, and save themes
    import uuid

    now = datetime.now()
    saved_count = 0

    for rank, theme_data in enumerate(themes_data[:limit], 1):
        theme_id = f"TH-{uuid.uuid4().hex[:12].upper()}"
        article_indices = theme_data.get("article_indices", [])
        sources = list({rows[i - 1].get("source", "") for i in article_indices if 0 < i <= len(rows)})

        theme = Theme(
            theme_id=theme_id,
            client_id="__GENERAL__",
            title=theme_data.get("title", ""),
            sentiment=theme_data.get("sentiment", "neutral"),
            article_count=len(article_indices),
            sources=sources,
            summary=theme_data.get("summary", ""),
            score=round(100 - (rank - 1) * 15, 2),
            rank=rank,
            generated_at=now,
            created_at=now,
            updated_at=now,
        )

        try:
            client.insert_theme(theme)
            saved_count += 1

            # Save article associations
            for idx in article_indices:
                if 0 < idx <= len(rows):
                    article_hash = rows[idx - 1].get("content_hash", "")
                    if article_hash:
                        assoc = ThemeArticleAssociation(
                            theme_id=theme_id,
                            article_hash=article_hash,
                            client_id="__GENERAL__",
                            created_at=now,
                        )
                        import contextlib

                        with contextlib.suppress(Exception):
                            client.insert_theme_article_association(assoc)
        except Exception as e:
            logger.warning("Failed to save theme %s: %s", theme_id, str(e))

    return {
        "success": True,
        "themes_generated": saved_count,
        "message": f"Successfully generated {saved_count} general market themes",
    }


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Crawl articles then generate general market themes."""
    try:
        mcp_arn = os.environ.get("WEB_CRAWLER_MCP_ARN")
        hours = int(os.environ.get("THEME_HOURS", "48"))
        limit = int(os.environ.get("THEME_LIMIT", "6"))

        # Step 1: Crawl fresh articles via WebCrawlerMcp (best-effort, may timeout)
        crawl_ok: bool | None = None
        crawl_error: str | None = None
        articles_saved = 0
        if mcp_arn:
            logger.info("Invoking WebCrawlerMcp to crawl articles")
            crawl_data = _crawl_articles_via_mcp(mcp_arn)
            crawl_ok = bool(crawl_data.get("success"))
            if not crawl_ok:
                crawl_error = crawl_data.get("error")
                # LOUD: a failed crawl means themes fall back to stale data.
                # Log at ERROR (was a swallowed WARNING) and surface the status
                # in the response so silent staleness cannot recur unnoticed.
                logger.error(
                    "Article crawl FAILED — themes will fall back to stale data. error=%s",
                    crawl_error,
                )
            else:
                articles_saved = crawl_data.get("articles_saved", 0)
                logger.info("Crawl saved %d articles", articles_saved)

        # Step 2: Generate themes directly (no MCP call — avoids 180s sandbox timeout)
        logger.info("Generating themes locally (hours=%d, limit=%d)", hours, limit)
        result = _generate_themes_locally(hours, limit)

        if not result.get("success"):
            raise RuntimeError(f"Theme generation failed: {result.get('error', 'Unknown error')}")

        logger.info("General theme generation completed: %s", result.get("message"))
        return {
            "statusCode": 200,
            "themes_generated": result.get("themes_generated", 0),
            "articles_saved": articles_saved,
            "crawl_ok": crawl_ok,
            "crawl_error": crawl_error,
            "hours": hours,
            "timestamp": datetime.now().isoformat(),
            "summary": result.get("message", "Theme generation completed"),
        }

    except Exception as e:
        error_msg = f"Failed to generate general themes: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "statusCode": 500,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "summary": error_msg,
        }
