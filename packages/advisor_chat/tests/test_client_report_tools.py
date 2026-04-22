"""Tests for database_agent/tools.py — PDF report retrieval and generation."""

from unittest.mock import patch

from wealth_management_portal_advisor_chat.database_agent.tools import (
    get_client_report_pdf,
)

_MOD = "wealth_management_portal_advisor_chat.database_agent.tools"


@patch(f"{_MOD}._presign", return_value="https://s3.example.com/report.pdf")
@patch(f"{_MOD}._latest_s3_report", return_value="reports/CL00001/RPT-ABC.pdf")
def test_existing_report_returned(mock_s3, mock_presign):
    with patch.dict("os.environ", {"REPORT_S3_BUCKET": "test-bucket"}):
        result = get_client_report_pdf._tool_func(client_id="CL00001")
    assert "Download Report" in result
    assert "RPT-ABC" in result
    mock_presign.assert_called_once()


@patch(f"{_MOD}._generate_report", return_value={"report_id": "RPT-NEW", "s3_path": "reports/CL00001/RPT-NEW.pdf"})
@patch(f"{_MOD}._presign", return_value="https://s3.example.com/new.pdf")
@patch(f"{_MOD}._latest_s3_report", return_value=None)
def test_generates_when_not_in_s3(mock_s3, mock_presign, mock_gen):
    with patch.dict("os.environ", {"REPORT_S3_BUCKET": "test-bucket"}):
        result = get_client_report_pdf._tool_func(client_id="CL00001")
    assert "freshly generated" in result
    assert "RPT-NEW" in result
    mock_gen.assert_called_once_with("CL00001")


@patch(f"{_MOD}._generate_report", side_effect=Exception("timeout"))
@patch(f"{_MOD}._latest_s3_report", return_value=None)
def test_generation_failure(mock_s3, mock_gen):
    with patch.dict("os.environ", {"REPORT_S3_BUCKET": "test-bucket"}):
        result = get_client_report_pdf._tool_func(client_id="CL00001")
    assert "Unable to retrieve" in result


def test_no_bucket_configured():
    with patch.dict("os.environ", {"REPORT_S3_BUCKET": ""}):
        result = get_client_report_pdf._tool_func(client_id="CL00001")
    assert "not configured" in result
