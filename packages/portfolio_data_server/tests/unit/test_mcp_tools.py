from unittest.mock import MagicMock, patch

from wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway import (
    _get_client_report_data,
    _list_clients,
)


def test_list_clients_returns_correct_structure():
    """Test that list_clients returns list of dicts with correct keys."""
    mock_client = MagicMock()
    mock_client.client_id = "CLT-001"
    mock_client.client_first_name = "John"
    mock_client.client_last_name = "Doe"
    mock_client.segment = "Premium"

    with patch(
        "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.create_simple_repos"
    ) as mock_repos:
        mock_repos.return_value = {"client": MagicMock(get=MagicMock(return_value=[mock_client]))}

        result = _list_clients({})

        assert isinstance(result, list)
        assert len(result) == 1
        client_dict = result[0]
        assert "client_id" in client_dict
        assert "client_first_name" in client_dict
        assert "client_last_name" in client_dict
        assert "segment" in client_dict
        assert client_dict["client_id"] == "CLT-001"
        assert client_dict["client_first_name"] == "John"
        assert client_dict["client_last_name"] == "Doe"
        assert client_dict["segment"] == "Premium"


def test_get_client_report_data_valid_client_returns_all_keys():
    """Test that get_client_report_data with valid client returns dict with all required keys."""
    mock_client = MagicMock()
    mock_client.client_id = "CLT-001"
    mock_client.model_dump = MagicMock(return_value={"client_id": "CLT-001"})

    mock_account = MagicMock()
    mock_account.account_id = "ACC-001"
    mock_account.model_dump = MagicMock(return_value={"account_id": "ACC-001"})

    mock_portfolio = MagicMock()
    mock_portfolio.portfolio_id = "PRT-001"
    mock_portfolio.model_dump = MagicMock(return_value={"portfolio_id": "PRT-001"})

    with (
        patch(
            "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.create_simple_repos"
        ) as mock_repos,
        patch(
            "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.ClientReportRepository"
        ) as mock_report_repo,
        patch(
            "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.InteractionRepository"
        ) as mock_interaction_repo,
    ):
        mock_repos.return_value = {
            "client": MagicMock(get_one=MagicMock(return_value=mock_client)),
            "restriction": MagicMock(get=MagicMock(return_value=[])),
            "account": MagicMock(get=MagicMock(return_value=[mock_account])),
            "income_expense": MagicMock(get=MagicMock(return_value=[])),
            "recommended_product": MagicMock(get=MagicMock(return_value=[])),
            "theme": MagicMock(get=MagicMock(return_value=[])),
        }

        mock_report_repo.return_value.get_portfolios.return_value = []
        mock_report_repo.return_value.get_holdings_with_securities.return_value = []
        mock_report_repo.return_value.get_performance.return_value = []
        mock_report_repo.return_value.get_transactions.return_value = []
        mock_interaction_repo.return_value.get_recent.return_value = []

        result = _get_client_report_data({"client_id": "CLT-001"})

        required_keys = [
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
        ]

        for key in required_keys:
            assert key in result

        assert isinstance(result["restrictions"], list)
        assert isinstance(result["accounts"], list)
        assert isinstance(result["portfolios"], list)
        assert isinstance(result["holdings_with_securities"], list)
        assert isinstance(result["performance"], list)
        assert isinstance(result["transactions"], list)
        assert isinstance(result["interactions"], list)
        assert isinstance(result["recommended_products"], list)
        assert isinstance(result["themes"], list)
        assert result["income_expense"] is None


def test_get_client_report_data_unknown_client_returns_error():
    """Test that get_client_report_data with unknown client returns error dict."""
    with patch(
        "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.create_simple_repos"
    ) as mock_repos:
        mock_repos.return_value = {"client": MagicMock(get_one=MagicMock(return_value=None))}

        result = _get_client_report_data({"client_id": "UNKNOWN"})

        assert "error" in result
        assert "Client 'UNKNOWN' not found" in result["error"]
        assert "Use list_clients to see available clients" in result["error"]


def test_get_client_report_data_no_portfolios_returns_empty_lists():
    """Test that get_client_report_data with no portfolios returns empty lists for portfolio-dependent fields."""
    mock_client = MagicMock()
    mock_client.client_id = "CLT-001"
    mock_client.model_dump = MagicMock(return_value={"client_id": "CLT-001"})

    with (
        patch(
            "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.create_simple_repos"
        ) as mock_repos,
        patch(
            "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.ClientReportRepository"
        ) as mock_report_repo,
        patch(
            "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.InteractionRepository"
        ) as mock_interaction_repo,
    ):
        mock_repos.return_value = {
            "client": MagicMock(get_one=MagicMock(return_value=mock_client)),
            "restriction": MagicMock(get=MagicMock(return_value=[])),
            "account": MagicMock(get=MagicMock(return_value=[])),
            "income_expense": MagicMock(get=MagicMock(return_value=[])),
            "recommended_product": MagicMock(get=MagicMock(return_value=[])),
            "theme": MagicMock(get=MagicMock(return_value=[])),
        }

        mock_report_repo.return_value.get_portfolios.return_value = []
        mock_report_repo.return_value.get_holdings_with_securities.return_value = []
        mock_report_repo.return_value.get_performance.return_value = []
        mock_report_repo.return_value.get_transactions.return_value = []
        mock_interaction_repo.return_value.get_recent.return_value = []

        result = _get_client_report_data({"client_id": "CLT-001"})

        assert result["portfolios"] == []
        assert result["holdings_with_securities"] == []
        assert result["performance"] == []
        assert result["transactions"] == []


def test_get_client_report_data_no_income_expense_returns_null():
    """Test that get_client_report_data with no income_expense returns null for that field."""
    mock_client = MagicMock()
    mock_client.client_id = "CLT-001"
    mock_client.model_dump = MagicMock(return_value={"client_id": "CLT-001"})

    with (
        patch(
            "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.create_simple_repos"
        ) as mock_repos,
        patch(
            "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.ClientReportRepository"
        ) as mock_report_repo,
        patch(
            "wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.InteractionRepository"
        ) as mock_interaction_repo,
    ):
        mock_repos.return_value = {
            "client": MagicMock(get_one=MagicMock(return_value=mock_client)),
            "restriction": MagicMock(get=MagicMock(return_value=[])),
            "account": MagicMock(get=MagicMock(return_value=[])),
            "income_expense": MagicMock(get=MagicMock(return_value=[])),
            "recommended_product": MagicMock(get=MagicMock(return_value=[])),
            "theme": MagicMock(get=MagicMock(return_value=[])),
        }

        mock_report_repo.return_value.get_portfolios.return_value = []
        mock_report_repo.return_value.get_holdings_with_securities.return_value = []
        mock_report_repo.return_value.get_performance.return_value = []
        mock_report_repo.return_value.get_transactions.return_value = []
        mock_interaction_repo.return_value.get_recent.return_value = []

        result = _get_client_report_data({"client_id": "CLT-001"})

        assert result["income_expense"] is None
