"""Report Agent — Strands SDK agent with MCP Gateway for data access.

Runs on AgentCore Runtime. Uses the Portfolio Data MCP Gateway for client data
fetching and report record saving, matching the pattern used by other agents.
"""

import logging
import os
import time
import uuid

import boto3
import uvicorn
from bedrock_agentcore.runtime.models import PingStatus
from common_auth import SigV4HTTPXAuth
from fastapi import HTTPException
from mcp.client.streamable_http import streamablehttp_client
from pydantic import BaseModel
from strands import Agent, tool
from strands.models.bedrock import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient

from .init import app

logger = logging.getLogger(__name__)


# --- MCP Gateway Connection ---


def _get_portfolio_mcp_client() -> MCPClient:
    """Connect to the Portfolio Data MCP Gateway via AgentCore."""
    gateway_url = os.environ["PORTFOLIO_GATEWAY_URL"]
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    region = os.getenv("AWS_REGION", "us-west-2")
    auth = SigV4HTTPXAuth(credentials, region)
    return MCPClient(lambda: streamablehttp_client(gateway_url, auth=auth, timeout=300, terminate_on_close=False))


# --- Strands Tools ---


@tool
def generate_next_best_action(profile_json: str, portfolio_json: str, communications_json: str) -> str:
    """Generate a personalized Next Best Action recommendation for the client.

    Uses Amazon Bedrock to analyze the client's profile, portfolio, and
    communications to produce actionable advice.
    """
    from .prompts import NEXT_BEST_ACTION_PROMPT

    prompt = NEXT_BEST_ACTION_PROMPT.format(
        profile_json=profile_json,
        portfolio_json=portfolio_json,
        communications_json=communications_json,
    )
    bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-west-2"))
    model_id = os.environ["REPORT_BEDROCK_MODEL_ID"]
    import json

    response = bedrock.invoke_model(
        modelId=model_id,
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 256,
                "messages": [{"role": "user", "content": prompt}],
            }
        ),
    )
    nba_text = json.loads(response["body"].read())["content"][0]["text"].strip()
    return nba_text[:1000] if nba_text else "No recommendation generated."


@tool
def generate_report_narratives(synthesis_prompts_json: str) -> str:
    """Generate AI narrative sections for the client report via Bedrock Converse.

    Uses forced tool-use to generate 7 sections: last_interaction_summary,
    recent_highlights, portfolio_narrative, financial_analysis, opportunities,
    relationship_context, action_items.
    """
    import json

    from .agent import invoke_narrative_generator

    prompts = json.loads(synthesis_prompts_json)
    narratives = invoke_narrative_generator({"synthesis_prompts": prompts})
    return json.dumps(narratives)


@tool
def assemble_and_upload_pdf(
    client_id: str,
    report_id: str,
    deterministic_sections: str,
    narratives_json: str,
    chart_svgs_json: str,
    next_best_action: str,
) -> str:
    """Assemble markdown from sections + narratives, convert to PDF, upload to S3.

    Uses WeasyPrint for PDF conversion. Uploads to REPORT_S3_BUCKET.
    """
    import json

    from ..pdf import html_to_pdf, markdown_to_html
    from .agent import assemble_markdown

    narratives = json.loads(narratives_json)
    chart_svgs = json.loads(chart_svgs_json)

    markdown = assemble_markdown(deterministic_sections, narratives)
    html = markdown_to_html(markdown, chart_svgs)
    pdf_bytes = html_to_pdf(html)

    # Upload PDF to S3
    s3_client = boto3.client("s3")
    bucket_name = os.environ["REPORT_S3_BUCKET"]
    s3_key = f"reports/{client_id}/{report_id}.pdf"
    s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=pdf_bytes, ContentType="application/pdf")

    return f"PDF uploaded: s3://{bucket_name}/{s3_key} ({len(pdf_bytes)} bytes)"


# --- Agent Definition ---

SYSTEM_PROMPT = """You are a report generation agent for a wealth management platform.

When given a client_id and report_id, execute these steps in order:
1. Call get_client_report_data (MCP tool) with the client_id to fetch all client data
2. Call generate_next_best_action with the client profile, portfolio, and communications data
3. Call generate_report_narratives with the synthesis_prompts from step 1
4. Call assemble_and_upload_pdf with all the pieces to create and upload the PDF
5. Call save_report (MCP tool) to persist the report record

Always call all steps in sequence. Do not skip any step.
After completion, respond with the report_id and s3_path.
"""


def create_report_agent() -> Agent:
    """Create the Report Agent with Strands SDK + MCP Gateway tools."""
    model_id = os.environ.get("REPORT_BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

    # Connect to Portfolio Data MCP Gateway for get_client_report_data and save_report
    mcp_client = _get_portfolio_mcp_client()

    return Agent(
        name="Report Agent",
        description="Generates comprehensive client briefing PDFs with AI narratives.",
        model=BedrockModel(model_id=model_id),
        system_prompt=SYSTEM_PROMPT,
        tools=[generate_next_best_action, generate_report_narratives, assemble_and_upload_pdf, mcp_client],
    )


# --- FastAPI Endpoint ---


class InvokeInput(BaseModel):
    client_id: str


@app.post("/invocations")
async def invoke(input: InvokeInput) -> dict:
    """Entry point for report generation via AgentCore Runtime."""
    t_start = time.time()
    import sys

    print(f"[REPORT-AGENT] /invocations called: client_id={input.client_id}", file=sys.stderr, flush=True)
    try:
        logger.info("Request received: client_id=%s", input.client_id)

        report_id = f"RPT-{uuid.uuid4().hex[:10].upper()}"

        # Run the Strands agent — it uses MCP Gateway for data + save, Bedrock for AI
        agent = create_report_agent()
        agent(
            f"Generate a full client report for client_id={input.client_id}. "
            f"Use report_id={report_id}. "
            f"The S3 path will be reports/{input.client_id}/{report_id}.pdf"
        )

        s3_key = f"reports/{input.client_id}/{report_id}.pdf"
        duration = time.time() - t_start
        logger.info(
            "Report generation succeeded: client_id=%s report_id=%s duration=%.2fs",
            input.client_id,
            report_id,
            duration,
        )
        return {"report_id": report_id, "s3_path": s3_key, "status": "complete"}

    except Exception as e:
        logger.exception("Report generation failed for %s", input.client_id)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/ping")
def ping() -> str:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    uvicorn.run("wealth_management_portal_report.report_agent.main:app", host="0.0.0.0", port=8080)
