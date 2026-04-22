"""Tests for report handler."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from wealth_management_portal_api.main import app

client = TestClient(app)


@patch("wealth_management_portal_api.report_handler.boto3.client")
@patch("wealth_management_portal_api.report_handler.ReportRepository")
def test_client_report_existing_complete(mock_repo_class, mock_boto3_client):
    """Test getting a complete report with presigned URL."""
    mock_report = MagicMock()
    mock_report.report_id = "report-123"
    mock_report.status = "complete"
    mock_report.s3_path = "reports/client-456/report-123.pdf"
    mock_report.next_best_action = None

    mock_repo = MagicMock()
    mock_repo.get_latest_by_client.return_value = mock_report
    mock_repo_class.return_value = mock_repo

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/presigned-url"
    mock_boto3_client.return_value = mock_s3

    response = client.get("/clients/client-456/report")

    assert response.status_code == 200
    data = response.json()
    assert data["report_id"] == "report-123"
    assert data["status"] == "complete"
    assert data["presigned_url"] == "https://s3.amazonaws.com/presigned-url"
    assert "next_best_action" in data


@patch("wealth_management_portal_api.report_handler.ReportRepository")
def test_client_report_not_found(mock_repo_class):
    """Test getting report when none exists."""
    mock_repo = MagicMock()
    mock_repo.get_latest_by_client.return_value = None
    mock_repo_class.return_value = mock_repo

    response = client.get("/clients/client-456/report")

    assert response.status_code == 200
    data = response.json()
    assert data["report_id"] is None
    assert data["status"] == "not_found"
    assert data["presigned_url"] is None
    assert "next_best_action" in data


@patch("wealth_management_portal_api.report_handler.ReportRepository")
def test_client_report_pending_no_url(mock_repo_class):
    """Test getting a pending report (no presigned URL)."""
    mock_report = MagicMock()
    mock_report.report_id = "report-789"
    mock_report.status = "pending"
    mock_report.s3_path = None
    mock_report.next_best_action = None

    mock_repo = MagicMock()
    mock_repo.get_latest_by_client.return_value = mock_report
    mock_repo_class.return_value = mock_repo

    response = client.get("/clients/client-456/report")

    assert response.status_code == 200
    data = response.json()
    assert data["report_id"] == "report-789"
    assert data["status"] == "pending"
    assert data["presigned_url"] is None
    assert "next_best_action" in data


@patch("wealth_management_portal_api.report_handler.ReportRepository")
def test_client_report_includes_next_best_action(mock_repo_class):
    """Test that a non-null next_best_action value is returned in the response."""
    mock_report = MagicMock()
    mock_report.report_id = "report-321"
    mock_report.status = "complete"
    mock_report.s3_path = None
    mock_report.next_best_action = "Schedule a portfolio review call"

    mock_repo = MagicMock()
    mock_repo.get_latest_by_client.return_value = mock_report
    mock_repo_class.return_value = mock_repo

    response = client.get("/clients/client-456/report")

    assert response.status_code == 200
    data = response.json()
    assert data["next_best_action"] == "Schedule a portfolio review call"
