import email.encoders
import email.mime.base
import email.mime.multipart
import email.mime.text
import os
import re

import boto3
import markdown
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

os.environ["POWERTOOLS_METRICS_NAMESPACE"] = "EmailSenderGateway"
os.environ["POWERTOOLS_SERVICE_NAME"] = "EmailSenderGateway"

logger: Logger = Logger()
metrics: Metrics = Metrics()
tracer: Tracer = Tracer()

_S3_URL_RE = re.compile(r"^s3://([^/]+)/(.+)$")
_SES_SENDER = os.environ.get("SES_SENDER_EMAIL", "")
if not _SES_SENDER:
    raise RuntimeError("SES_SENDER_EMAIL environment variable is required")


def _style_tables(html: str) -> str:
    """Inject inline styles on table elements for email client compatibility."""
    cell_style = "border:1px solid #ccc;padding:6px 10px;text-align:left"
    html = html.replace("<table>", '<table style="border-collapse:collapse;width:100%">')
    html = html.replace("<th>", f'<th style="{cell_style};font-weight:bold">')
    html = html.replace("<td>", f'<td style="{cell_style}">')
    return html


def _to_html(body: str) -> str:
    """Convert markdown body to a self-contained HTML string."""
    content = markdown.markdown(body, extensions=["tables"])
    content = _style_tables(content)
    return f'<html><body style="font-family:sans-serif;line-height:1.6;">{content}</body></html>'


def _send_email(event: dict) -> dict:
    to = event.get("to")
    subject = event.get("subject")
    body = event.get("body", "")
    attachment_url = event.get("attachment_url")

    if not to:
        return {"error": "Missing required field: to"}
    if not subject:
        return {"error": "Missing required field: subject"}

    ses = boto3.client("ses")

    if not attachment_url:
        ses.send_email(
            Source=_SES_SENDER,
            Destination={"ToAddresses": [to]},
            Message={"Subject": {"Data": subject}, "Body": {"Html": {"Data": _to_html(body)}, "Text": {"Data": body}}},
        )
        return {"message": f"Email sent to {to}"}

    # Parse S3 URL
    match = _S3_URL_RE.match(attachment_url)
    if not match:
        return {"error": f"Invalid S3 URL: {attachment_url}. Expected format: s3://bucket/key"}

    bucket, key = match.group(1), match.group(2)
    s3 = boto3.client("s3")
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except s3.exceptions.NoSuchKey:
        return {"error": f"S3 object not found: {attachment_url}"}
    except Exception as e:
        return {"error": f"Failed to fetch S3 object: {e}"}

    file_data = obj["Body"].read()
    filename = key.split("/")[-1]
    content_type = obj.get("ContentType", "application/octet-stream")

    msg = email.mime.multipart.MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = _SES_SENDER
    msg["To"] = to
    # Build alternative part so clients can choose plain or HTML
    alt = email.mime.multipart.MIMEMultipart("alternative")
    alt.attach(email.mime.text.MIMEText(body, "plain"))
    alt.attach(email.mime.text.MIMEText(_to_html(body), "html"))
    msg.attach(alt)

    maintype, _, subtype = content_type.partition("/")
    subtype = subtype or "octet-stream"
    maintype = maintype or "application"
    part = email.mime.base.MIMEBase(maintype, subtype)
    part.set_payload(file_data)
    email.encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(part)

    ses.send_raw_email(
        Source=_SES_SENDER,
        Destinations=[to],
        RawMessage={"Data": msg.as_bytes()},
    )
    return {"message": f"Email with attachment sent to {to}"}


_DISPATCH = {
    "send_email": _send_email,
}


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext):
    logger.info("Received event", extra={"event": event})
    metrics.add_metric(name="InvocationCount", unit=MetricUnit.Count, value=1)

    try:
        tool_full_name = context.client_context.custom["bedrockAgentCoreToolName"]
        tool_name = tool_full_name.split("___")[-1]
        logger.info("Dispatching tool", extra={"tool_name": tool_name})

        handler_fn = _DISPATCH.get(tool_name)
        if not handler_fn:
            raise ValueError(f"Unknown tool: {tool_name}")

        result = handler_fn(event)
        metrics.add_metric(name="SuccessCount", unit=MetricUnit.Count, value=1)
        return result

    except Exception as e:
        logger.exception("Tool invocation failed")
        metrics.add_metric(name="ErrorCount", unit=MetricUnit.Count, value=1)
        return {"error": str(e)}
