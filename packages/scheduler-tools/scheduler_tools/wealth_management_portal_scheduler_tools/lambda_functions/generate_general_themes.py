"""
Lambda handler for generating general market themes via Web Crawler MCP.
"""

import json
import os
import traceback
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from common_auth import SigV4HTTPXAuth
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = Logger()
tracer = Tracer()


def _build_url(arn: str, region: str) -> str:
    encoded = arn.replace(":", "%3A").replace("/", "%2F")
    return f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded}/invocations?qualifier=DEFAULT"


def _invoke_web_crawler_mcp(mcp_arn: str, tool_name: str, arguments: dict) -> dict:
    region = os.environ.get("AWS_REGION", "us-west-2")
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    url = _build_url(mcp_arn, region)
    mcp_client = MCPClient(
        lambda: streamablehttp_client(url, auth=SigV4HTTPXAuth(creds, region), timeout=900, terminate_on_close=False)
    )
    with mcp_client as client:
        result = client.call_tool_sync(tool_name, name=tool_name, arguments=arguments)
    return json.loads(result["content"][0]["text"])


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Crawl articles then generate general market themes via Web Crawler MCP."""
    try:
        mcp_arn = os.environ.get("WEB_CRAWLER_MCP_ARN")
        if not mcp_arn:
            raise ValueError("WEB_CRAWLER_MCP_ARN environment variable not set")

        hours = int(os.environ.get("THEME_HOURS", "48"))
        limit = int(os.environ.get("THEME_LIMIT", "6"))

        logger.info("Invoking MCP tool: save_articles_to_redshift")
        crawl_data = _invoke_web_crawler_mcp(mcp_arn, "save_articles_to_redshift", {"rss_only": True})
        if not crawl_data.get("success"):
            logger.warning(f"Crawl had issues: {crawl_data.get('error')} — continuing with existing articles")
        else:
            save_errors = crawl_data.get("save_errors", [])
            if save_errors:
                logger.warning(
                    "Crawl saved %d articles but %d failed: %s",
                    crawl_data.get("articles_saved", 0),
                    len(save_errors),
                    save_errors[0],
                )
            else:
                logger.info(f"Crawl saved {crawl_data.get('articles_saved', 0)} articles")

        logger.info(f"Invoking MCP tool: generate_general_themes (hours={hours}, limit={limit})")
        result = _invoke_web_crawler_mcp(mcp_arn, "generate_general_themes", {"hours": hours, "limit": limit})

        if not result.get("success"):
            raise RuntimeError(f"Theme generation failed: {result.get('error', 'Unknown error')}")

        logger.info("General theme generation completed successfully")
        return {
            "statusCode": 200,
            "articles_saved": crawl_data.get("articles_saved", 0),
            "themes_generated": result.get("themes_generated", 0),
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
