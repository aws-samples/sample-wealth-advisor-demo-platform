"""Integration tests for Email Sender against real SES and S3."""

import os
from unittest.mock import MagicMock

import boto3
import pytest

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("SES_SENDER_EMAIL"),
        reason="SES_SENDER_EMAIL not set",
    ),
    pytest.mark.integration,
]

SES_SENDER_EMAIL = os.environ.get("SES_SENDER_EMAIL", "")
TEST_RECIPIENT_EMAIL = os.environ.get("TEST_RECIPIENT_EMAIL", SES_SENDER_EMAIL)
TEST_S3_BUCKET = os.environ.get("TEST_S3_BUCKET", "")

_uploaded_keys: list[str] = []


def _context(tool_name: str):
    ctx = MagicMock()
    ctx.client_context.custom = {"bedrockAgentCoreToolName": f"gateway___email___{tool_name}"}
    return ctx


@pytest.fixture(autouse=True)
def cleanup_s3():
    yield
    if TEST_S3_BUCKET and _uploaded_keys:
        s3 = boto3.client("s3")
        for key in _uploaded_keys:
            s3.delete_object(Bucket=TEST_S3_BUCKET, Key=key)
        _uploaded_keys.clear()


def test_plain_text_email():
    from wealth_management_portal_email_sender_mcp.lambda_functions.email_sender_gateway import lambda_handler

    event = {
        "to": TEST_RECIPIENT_EMAIL,
        "subject": "Integration Test — Plain Text",
        "body": "This is an integration test email.",
    }
    result = lambda_handler(event, _context("send_email"))
    assert "error" not in result
    assert "message" in result


@pytest.mark.skipif(not os.environ.get("TEST_S3_BUCKET"), reason="TEST_S3_BUCKET not set")
def test_email_with_s3_attachment():
    from wealth_management_portal_email_sender_mcp.lambda_functions.email_sender_gateway import lambda_handler

    key = "integration-test/attachment.txt"
    s3 = boto3.client("s3")
    s3.put_object(Bucket=TEST_S3_BUCKET, Key=key, Body=b"Test attachment content", ContentType="text/plain")
    _uploaded_keys.append(key)

    event = {
        "to": TEST_RECIPIENT_EMAIL,
        "subject": "Integration Test — With Attachment",
        "body": "See attached file.",
        "attachment_url": f"s3://{TEST_S3_BUCKET}/{key}",
    }
    result = lambda_handler(event, _context("send_email"))
    assert "error" not in result
    assert "message" in result


def test_unverified_recipient_handled_gracefully():
    """In SES sandbox mode, sending to unverified address returns an error gracefully."""
    from wealth_management_portal_email_sender_mcp.lambda_functions.email_sender_gateway import lambda_handler

    event = {
        "to": "unverified-address-xyz@example-nonexistent-domain.invalid",
        "subject": "Integration Test — Unverified",
        "body": "This should fail gracefully.",
    }
    result = lambda_handler(event, _context("send_email"))
    # Either succeeds (production SES) or returns an error dict (sandbox)
    assert isinstance(result, dict)
    # If error, it should be a string message, not an exception
    if "error" in result:
        assert isinstance(result["error"], str)
