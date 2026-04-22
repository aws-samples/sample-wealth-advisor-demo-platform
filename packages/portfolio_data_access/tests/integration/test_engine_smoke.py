# Smoke test — verifies IAM connection factory can reach Redshift Serverless.
# This is a temporary integration test. Delete after confirming the connection works.
import pytest

from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory


@pytest.mark.integration
def test_iam_connection():
    """Verify IAM connection factory can connect and execute a query."""
    connect = iam_connection_factory()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        result = cur.fetchone()
    assert result[0] == 1
