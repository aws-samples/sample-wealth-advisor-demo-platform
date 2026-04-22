import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env from the portfolio_data_server package root
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway import (  # noqa: E402
    _get_client_report_data,
)

pytestmark = [
    pytest.mark.skipif(not os.environ.get("REDSHIFT_DATABASE"), reason="Redshift not available"),
    pytest.mark.integration,
]


def test_get_client_report_data_returns_all_keys():
    """Verify get_client_report_data returns complete report data from Redshift."""
    result = _get_client_report_data({"client_id": "CL00014"})

    # Should not be an error
    assert "error" not in result

    # All 11 keys present
    expected_keys = {
        "client",
        "restrictions",
        "accounts",
        "portfolios",
        "holdings_with_securities",
        "performance",
        "transactions",
        "interactions",
        "income_expense",
        "recommended_products",
        "themes",
    }
    assert set(result.keys()) == expected_keys

    # Client is correct
    assert result["client"]["client_id"] == "CL00014"

    # List fields are non-empty lists
    for key in ["accounts", "portfolios", "holdings_with_securities", "performance", "transactions"]:
        assert isinstance(result[key], list), f"{key} should be a list"
        assert len(result[key]) > 0, f"{key} should not be empty for CL00014"

    # Holdings span multiple portfolios (bug fix validation)
    portfolio_ids_in_holdings = {h["portfolio_id"] for h in result["holdings_with_securities"]}
    assert len(portfolio_ids_in_holdings) >= 1

    # Transactions span multiple accounts (bug fix validation)
    account_ids_in_txns = {t["account_id"] for t in result["transactions"]}
    assert len(account_ids_in_txns) >= 1


def test_get_client_report_data_unknown_client():
    """Verify unknown client returns error."""
    result = _get_client_report_data({"client_id": "NONEXISTENT"})
    assert "error" in result
