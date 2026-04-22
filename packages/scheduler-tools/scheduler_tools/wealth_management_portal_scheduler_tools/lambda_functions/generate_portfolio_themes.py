"""
Lambda handler for generating portfolio-specific themes for a client via Web Crawler MCP.
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
    """Generate portfolio-specific themes for a single client via Web Crawler MCP."""
    try:
        client_id = event.get("client_id")
        if not client_id:
            raise ValueError("client_id is required in event")

        mcp_arn = os.environ.get("WEB_CRAWLER_MCP_ARN")
        if not mcp_arn:
            raise ValueError("WEB_CRAWLER_MCP_ARN environment variable not set")

        top_n_stocks = int(os.environ.get("TOP_N_STOCKS", "5"))
        themes_per_stock = int(os.environ.get("THEMES_PER_STOCK", "2"))
        hours = int(os.environ.get("THEME_HOURS", "48"))

        logger.info(f"Starting portfolio theme generation for client: {client_id}")
        result = _invoke_web_crawler_mcp(
            mcp_arn,
            "generate_portfolio_themes_for_client",
            {
                "client_id": client_id,
                "top_n_stocks": top_n_stocks,
                "themes_per_stock": themes_per_stock,
                "hours": hours,
            },
        )

        if not result.get("success"):
            raise RuntimeError(f"Portfolio theme generation failed: {result.get('error', 'Unknown error')}")

        logger.info(f"Portfolio theme generation completed: {result.get('themes_generated', 0)} themes")
        return {
            "statusCode": 200,
            "client_id": client_id,
            "themes_generated": result.get("themes_generated", 0),
            "stocks_covered": result.get("stocks_covered", 0),
            "top_n_stocks": top_n_stocks,
            "themes_per_stock": themes_per_stock,
            "hours": hours,
            "timestamp": datetime.now().isoformat(),
            "summary": result.get("message", "Portfolio theme generation completed"),
        }

    except Exception as e:
        error_msg = f"Failed to generate portfolio themes: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "statusCode": 500,
            "client_id": event.get("client_id"),
            "error": str(e),
            "traceback": traceback.format_exc(),
            "summary": error_msg,
        }
