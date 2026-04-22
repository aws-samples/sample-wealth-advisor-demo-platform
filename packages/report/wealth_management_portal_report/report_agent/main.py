import logging
import os
import time
import uuid
from datetime import UTC, datetime

import boto3
import uvicorn
from bedrock_agentcore.runtime.models import PingStatus
from fastapi import HTTPException
from pydantic import BaseModel

from ..pdf import html_to_pdf, markdown_to_html
from .agent import assemble_markdown, invoke_narrative_generator
from .init import app
from .tools import _get_mcp_client, fetch_report_data, generate_next_best_action, save_report_via_mcp

logger = logging.getLogger(__name__)


class InvokeInput(BaseModel):
    client_id: str


@app.post("/invocations")
async def invoke(input: InvokeInput) -> dict:
    """Entry point for synchronous report generation"""
    t_start = time.time()
    try:
        logger.info("Request received: client_id=%s", input.client_id)

        # Generate report ID
        report_id = f"RPT-{uuid.uuid4().hex[:10].upper()}"

        # Fetch report data
        mcp_client = _get_mcp_client()
        with mcp_client as client:
            logger.info("MCP client connected, resolving tool names")

            logger.info("fetch_report_data started: client_id=%s", input.client_id)
            report_data = fetch_report_data(input.client_id, mcp_client=client)
            logger.info("fetch_report_data completed: keys=%s", list(report_data.components.keys()))

            # Generate Next Best Action via a direct Bedrock call, independent of the report agent.
            # Failure is non-fatal — NBA defaults to None so report generation is not blocked.
            next_best_action = None
            try:
                next_best_action = generate_next_best_action(report_data)
                logger.info("NBA generated: length=%d", len(next_best_action) if next_best_action else 0)
            except Exception:
                logger.exception("NBA generation failed; continuing without NBA")

            # Generate narratives via Bedrock Converse tool use
            logger.info("Narrative generation started")
            narratives = invoke_narrative_generator(report_data.components)
            logger.info("Narrative generation completed: sections=%d", len(narratives))
            logger.info("Markdown assembly started")
            markdown = assemble_markdown(report_data.components["deterministic_sections"], narratives)
            logger.info("Markdown assembled: length=%d", len(markdown))

            # Convert markdown to PDF
            logger.info("PDF generation started")
            html = markdown_to_html(markdown, report_data.components["chart_svgs"])
            pdf_bytes = html_to_pdf(html)
            logger.info("PDF generation completed: pdf_size_bytes=%d", len(pdf_bytes))

            # Upload PDF to S3
            s3_client = boto3.client("s3")
            bucket_name = os.environ["REPORT_S3_BUCKET"]
            s3_key = f"reports/{input.client_id}/{report_id}.pdf"

            logger.info("S3 upload started: s3_path=%s", s3_key)
            s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=pdf_bytes, ContentType="application/pdf")
            logger.info("S3 upload completed: s3_path=%s", s3_key)

            # Save report record via MCP
            logger.info("save_report started: report_id=%s", report_id)
            save_report_via_mcp(
                report_id=report_id,
                client_id=input.client_id,
                s3_path=s3_key,
                generated_date=datetime.now(UTC).isoformat(),
                status="complete",
                next_best_action=next_best_action,
                mcp_client=client,
            )
            logger.info("save_report completed: report_id=%s", report_id)

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
    uvicorn.run("wealth_management_portal_report.report_agent.main:app", port=8080)
