"""Database agent tools — PDF report generation."""

import json
import logging
import os

import boto3
import botocore.config
import requests
from strands import tool

logger = logging.getLogger(__name__)

REPORT_AGENT_URL = os.environ.get("REPORT_AGENT_URL", "http://localhost:8080")
REPORT_AGENT_ARN = os.environ.get("REPORT_AGENT_ARN", "")


def _presign(bucket: str, key: str) -> str:
    return boto3.client("s3").generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600
    )


def _latest_s3_report(bucket: str, client_id: str) -> str | None:
    """Return the S3 key of the most recent PDF for *client_id*, or None."""
    s3 = boto3.client("s3")
    prefix = f"reports/{client_id}/"
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    objects = [o for o in resp.get("Contents", []) if o["Key"].endswith(".pdf")]
    if not objects:
        return None
    objects.sort(key=lambda o: o["LastModified"], reverse=True)
    return objects[0]["Key"]


def _generate_report(client_id: str) -> dict:
    """Call the report agent to generate a new PDF. Returns {"report_id", "s3_path", "status"}."""
    if REPORT_AGENT_ARN:
        client = boto3.client(
            "bedrock-agentcore",
            region_name=os.environ.get("AWS_REGION", "us-west-2"),
            config=botocore.config.Config(read_timeout=120),
        )
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=REPORT_AGENT_ARN,
            runtimeSessionId=f"report-{client_id}",
            payload=json.dumps({"client_id": client_id}).encode(),
        )
        return json.loads(resp["response"].read())
    resp = requests.post(f"{REPORT_AGENT_URL}/invocations", json={"client_id": client_id}, timeout=120)
    resp.raise_for_status()
    return resp.json()


@tool
def get_client_report_pdf(client_id: str) -> str:
    """Get the latest PDF report for a client as a downloadable link.

    Checks S3 for an existing report first. If none exists, invokes the
    report generation agent to create one.

    Use when advisor asks to "show report", "get report", "download report",
    or "pull report" for a client.

    Args:
        client_id: The client ID (e.g. CL00001).

    Returns:
        Markdown link to download the PDF report, or status message.
    """
    bucket = os.environ.get("REPORT_S3_BUCKET", "")
    if not bucket:
        return "Report storage not configured (REPORT_S3_BUCKET)."

    # 1. Check S3 for existing report
    try:
        key = _latest_s3_report(bucket, client_id)
        if key:
            url = _presign(bucket, key)
            report_id = key.rsplit("/", 1)[-1].replace(".pdf", "")
            return (
                f"📄 **Client Report — {client_id}**\n\n"
                f"Report ID: {report_id}\n\n"
                f"[📥 Download Report (PDF)]({url})\n\n"
                f"*Link expires in 1 hour.*"
            )
    except Exception:
        logger.exception("S3 lookup failed for %s, will try generating", client_id)

    # 2. No existing report — generate one
    try:
        result = _generate_report(client_id)
        s3_path = result.get("s3_path", "")
        report_id = result.get("report_id", "")
        if not s3_path:
            return f"Report generation completed but no file path returned for {client_id}."
        url = _presign(bucket, s3_path)
        return (
            f"📄 **Client Report — {client_id}** (freshly generated)\n\n"
            f"Report ID: {report_id}\n\n"
            f"[📥 Download Report (PDF)]({url})\n\n"
            f"*Link expires in 1 hour.*"
        )
    except Exception:
        logger.exception("Report generation failed for %s", client_id)
        return f"Unable to retrieve or generate a report for {client_id}. Please try again later."
