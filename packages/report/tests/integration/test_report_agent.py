# Integration test for report agent — uses real Redshift client IDs
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import boto3
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Load package .env, then root .env as fallback for vars like AWS_ACCOUNT_ID
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent.parent / ".env", override=False)

from wealth_management_portal_report.pdf import html_to_pdf, markdown_to_html  # noqa: E402
from wealth_management_portal_report.report_agent import tools as _tools  # noqa: E402
from wealth_management_portal_report.report_agent.agent import (  # noqa: E402
    assemble_markdown,
    invoke_narrative_generator,
)

pytestmark = [
    pytest.mark.skipif(not os.environ.get("REDSHIFT_DATABASE"), reason="Redshift not available"),
    pytest.mark.integration,
]

REPORTS_DIR = Path(__file__).parent.parent / "reports"

# Real Redshift client IDs used for testing
CLIENT_1_ID = "CL00014"  # has market theme data
CLIENT_2_ID = "CL00031"  # has market theme data


@pytest.fixture(autouse=True)
def setup_reports_dir():
    """Ensure reports directory exists."""
    REPORTS_DIR.mkdir(exist_ok=True)


class TestReportAgent:
    """Integration tests for report agent."""

    def test_generate_report_client_1(self):
        """Test report generation for client CL00014."""
        report_data = _tools.fetch_report_data(CLIENT_1_ID)
        narratives = invoke_narrative_generator(report_data.components)
        final_markdown = assemble_markdown(report_data.components["deterministic_sections"], narratives)
        (REPORTS_DIR / f"{CLIENT_1_ID}_report.md").write_text(final_markdown)
        assert CLIENT_1_ID in final_markdown

    def test_generate_report_client_2(self):
        """Test report generation for client CL00031."""
        report_data = _tools.fetch_report_data(CLIENT_2_ID)
        narratives = invoke_narrative_generator(report_data.components)
        final_markdown = assemble_markdown(report_data.components["deterministic_sections"], narratives)
        (REPORTS_DIR / f"{CLIENT_2_ID}_report.md").write_text(final_markdown)
        assert CLIENT_2_ID in final_markdown

    @pytest.mark.parametrize("client_id", [CLIENT_1_ID, CLIENT_2_ID])
    def test_generate_pdf_report(self, client_id: str):
        """Test PDF generation for each client."""
        report_data = _tools.fetch_report_data(client_id)
        narratives = invoke_narrative_generator(report_data.components)
        markdown = assemble_markdown(report_data.components["deterministic_sections"], narratives)

        pdf_bytes = html_to_pdf(markdown_to_html(markdown, report_data.components["chart_svgs"]))
        (REPORTS_DIR / f"{client_id}_report.pdf").write_bytes(pdf_bytes)

        assert pdf_bytes.startswith(b"%PDF")

    def test_invalid_client(self):
        """Test error handling for an invalid client ID."""
        with pytest.raises(RuntimeError):
            _tools.fetch_report_data("CLT-INVALID")

    def test_nba_generation(self):
        """Test NBA generation via direct Bedrock call using real client data."""
        report_data = _tools.fetch_report_data(CLIENT_1_ID)
        nba = _tools.generate_next_best_action(report_data)
        print(f"\nNBA for {CLIENT_1_ID}: {nba}")
        assert nba is not None
        assert len(nba) > 0
        assert len(nba) <= 1000

    @pytest.mark.parametrize("client_id", [CLIENT_1_ID, CLIENT_2_ID])
    def test_invocations_generates_pdf_report(self, client_id: str):
        """Test /invocations end-to-end with real Redshift, Bedrock, and MCP.

        Only S3 is mocked to avoid uploading to a real bucket.
        """
        from wealth_management_portal_report.report_agent.main import app

        mock_s3_client = MagicMock()

        # Mock only S3 client creation; let Bedrock calls (NBA generation) use real boto3
        original_boto3_client = boto3.client

        def selective_mock(service, **kwargs):
            if service == "s3":
                return mock_s3_client
            return original_boto3_client(service, **kwargs)

        with patch("wealth_management_portal_report.report_agent.main.boto3") as mock_boto3:
            mock_boto3.client.side_effect = selective_mock
            mock_boto3.Session = boto3.Session

            with patch.dict(os.environ, {"REPORT_S3_BUCKET": "test-report-bucket"}):
                response = TestClient(app).post("/invocations", json={"client_id": client_id})

            if response.status_code != 200:
                print(f"Error response: {response.status_code}")
                print(f"Error detail: {response.text}")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "complete"
            assert data["report_id"].startswith("RPT-")
            assert data["s3_path"] == f"reports/{client_id}/{data['report_id']}.pdf"

            # Extract PDF from mocked S3 put_object call
            pdf_bytes = mock_s3_client.put_object.call_args.kwargs["Body"]
            assert pdf_bytes.startswith(b"%PDF")
            assert len(pdf_bytes) > 10000, (
                f"PDF size {len(pdf_bytes)} bytes is too small, expected >10KB with real data"
            )

            # Save locally for inspection
            (REPORTS_DIR / f"{client_id}_invocations_report.pdf").write_bytes(pdf_bytes)
