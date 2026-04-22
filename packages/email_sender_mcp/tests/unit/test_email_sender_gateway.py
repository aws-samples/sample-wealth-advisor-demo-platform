import os
from io import BytesIO
from unittest.mock import MagicMock, patch

os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "EmailSenderGateway")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "EmailSenderGateway")
os.environ.setdefault("SES_SENDER_EMAIL", "sender@example.com")

from wealth_management_portal_email_sender_mcp.lambda_functions.email_sender_gateway import lambda_handler  # noqa: E402


def _context(tool_name: str):
    ctx = MagicMock()
    ctx.client_context.custom = {"bedrockAgentCoreToolName": f"gateway___email___{tool_name}"}
    return ctx


@patch("wealth_management_portal_email_sender_mcp.lambda_functions.email_sender_gateway.boto3")
def test_plain_text_email(mock_boto3):
    ses = MagicMock()
    mock_boto3.client.return_value = ses

    event = {"to": "user@example.com", "subject": "Hello", "body": "World"}
    result = lambda_handler(event, _context("send_email"))

    assert "message" in result
    mock_boto3.client.assert_called_once_with("ses")
    call_kwargs = ses.send_email.call_args[1]
    body_arg = call_kwargs["Message"]["Body"]
    assert body_arg["Text"]["Data"] == "World"
    assert "<p>World</p>" in body_arg["Html"]["Data"]
    ses.send_raw_email.assert_not_called()


@patch("wealth_management_portal_email_sender_mcp.lambda_functions.email_sender_gateway.boto3")
def test_email_with_s3_attachment(mock_boto3):
    ses = MagicMock()
    s3 = MagicMock()

    def client_factory(service):
        return ses if service == "ses" else s3

    mock_boto3.client.side_effect = client_factory

    file_content = b"PDF content here"
    s3.get_object.return_value = {
        "Body": BytesIO(file_content),
        "ContentType": "application/pdf",
    }

    event = {
        "to": "user@example.com",
        "subject": "Report",
        "body": "See attached",
        "attachment_url": "s3://my-bucket/reports/report.pdf",
    }
    result = lambda_handler(event, _context("send_email"))

    assert "message" in result
    s3.get_object.assert_called_once_with(Bucket="my-bucket", Key="reports/report.pdf")
    ses.send_raw_email.assert_called_once()
    ses.send_email.assert_not_called()


@patch("wealth_management_portal_email_sender_mcp.lambda_functions.email_sender_gateway.boto3")
def test_mime_structure(mock_boto3):
    """Verify MIME multipart has text part + attachment part with correct content-type."""
    import email as email_lib

    ses = MagicMock()
    s3 = MagicMock()
    mock_boto3.client.side_effect = lambda svc: ses if svc == "ses" else s3

    s3.get_object.return_value = {
        "Body": BytesIO(b"data"),
        "ContentType": "application/pdf",
    }

    event = {
        "to": "user@example.com",
        "subject": "Test",
        "body": "Body text",
        "attachment_url": "s3://bucket/file.pdf",
    }
    lambda_handler(event, _context("send_email"))

    raw_bytes = ses.send_raw_email.call_args[1]["RawMessage"]["Data"]
    msg = email_lib.message_from_bytes(raw_bytes)

    parts = list(msg.walk())
    content_types = [p.get_content_type() for p in parts]
    assert "text/plain" in content_types
    assert "text/html" in content_types
    assert "application/pdf" in content_types

    attachment_part = next(p for p in parts if p.get_content_type() == "application/pdf")
    assert attachment_part.get_filename() == "file.pdf"


@patch("wealth_management_portal_email_sender_mcp.lambda_functions.email_sender_gateway.boto3")
def test_markdown_converted_to_html(mock_boto3):
    ses = MagicMock()
    mock_boto3.client.return_value = ses

    body = "**bold** text\n\n| Col1 | Col2 |\n| --- | --- |\n| a | b |"
    event = {"to": "user@example.com", "subject": "MD Test", "body": body}
    lambda_handler(event, _context("send_email"))

    html = ses.send_email.call_args[1]["Message"]["Body"]["Html"]["Data"]
    assert "<strong>bold</strong>" in html
    # Tables should have inline border and alignment styles for email client compatibility
    assert "border-collapse:collapse" in html
    assert "border:1px solid #ccc" in html
    assert "text-align:left" in html


def test_missing_to():
    result = lambda_handler({"subject": "Hi", "body": "text"}, _context("send_email"))
    assert "error" in result
    assert "to" in result["error"]


def test_missing_subject():
    result = lambda_handler({"to": "user@example.com", "body": "text"}, _context("send_email"))
    assert "error" in result
    assert "subject" in result["error"]


@patch("wealth_management_portal_email_sender_mcp.lambda_functions.email_sender_gateway.boto3")
def test_invalid_s3_url(mock_boto3):
    ses = MagicMock()
    mock_boto3.client.return_value = ses

    event = {
        "to": "user@example.com",
        "subject": "Hi",
        "body": "text",
        "attachment_url": "https://not-an-s3-url.com/file.pdf",
    }
    result = lambda_handler(event, _context("send_email"))
    assert "error" in result
    assert "Invalid S3 URL" in result["error"]
    ses.send_email.assert_not_called()
    ses.send_raw_email.assert_not_called()


@patch("wealth_management_portal_email_sender_mcp.lambda_functions.email_sender_gateway.boto3")
def test_s3_object_not_found(mock_boto3):
    ses = MagicMock()
    s3 = MagicMock()
    mock_boto3.client.side_effect = lambda svc: ses if svc == "ses" else s3

    # Simulate NoSuchKey via exceptions attribute
    s3.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
    s3.get_object.side_effect = s3.exceptions.NoSuchKey("Not found")

    event = {
        "to": "user@example.com",
        "subject": "Hi",
        "body": "text",
        "attachment_url": "s3://bucket/missing.pdf",
    }
    result = lambda_handler(event, _context("send_email"))
    assert "error" in result
    assert "not found" in result["error"].lower()


def test_unknown_tool():
    result = lambda_handler({}, _context("nonexistent_tool"))
    assert "error" in result
