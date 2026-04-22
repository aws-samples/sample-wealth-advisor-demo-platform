from unittest.mock import Mock, patch

import pytest

from wealth_management_portal_scheduler_tools.lambda_functions.get_client_list import lambda_handler


def test_handler_splits_into_test_and_remaining():
    """Test handler splits client IDs into test batch and remaining."""
    mock_clients = [{"client_id": f"CLT-{i:03d}"} for i in range(1, 8)]

    with patch(
        "wealth_management_portal_scheduler_tools.lambda_functions.get_client_list.ClientRepository"
    ) as mock_repo_cls:
        mock_repo_cls.return_value.get_all_clients.return_value = mock_clients

        result = lambda_handler({}, Mock())

        assert result["test_client_ids"] == ["CLT-001", "CLT-002", "CLT-003"]
        assert result["remaining_client_ids"] == ["CLT-004", "CLT-005", "CLT-006", "CLT-007"]
        assert result["count"] == 7


def test_handler_paginates_all_clients():
    """Test handler paginates through all pages of clients."""
    page1 = [{"client_id": f"CLT-{i:03d}"} for i in range(1, 101)]
    page2 = [{"client_id": f"CLT-{i:03d}"} for i in range(101, 120)]

    with patch(
        "wealth_management_portal_scheduler_tools.lambda_functions.get_client_list.ClientRepository"
    ) as mock_repo_cls:
        mock_repo_cls.return_value.get_all_clients.side_effect = [page1, page2]

        result = lambda_handler({}, Mock())

        assert result["count"] == 119
        assert len(result["test_client_ids"]) == 3
        assert len(result["remaining_client_ids"]) == 116


def test_handler_returns_empty_lists_when_no_clients():
    """Test handler returns empty lists when no clients."""
    with patch(
        "wealth_management_portal_scheduler_tools.lambda_functions.get_client_list.ClientRepository"
    ) as mock_repo_cls:
        mock_repo_cls.return_value.get_all_clients.return_value = []

        result = lambda_handler({}, Mock())

        assert result["test_client_ids"] == []
        assert result["remaining_client_ids"] == []
        assert result["count"] == 0


def test_handler_fewer_clients_than_test_batch():
    """Test handler with fewer clients than TEST_BATCH_SIZE puts all in test."""
    mock_clients = [{"client_id": "CLT-001"}, {"client_id": "CLT-002"}]

    with patch(
        "wealth_management_portal_scheduler_tools.lambda_functions.get_client_list.ClientRepository"
    ) as mock_repo_cls:
        mock_repo_cls.return_value.get_all_clients.return_value = mock_clients

        result = lambda_handler({}, Mock())

        assert result["test_client_ids"] == ["CLT-001", "CLT-002"]
        assert result["remaining_client_ids"] == []
        assert result["count"] == 2


def test_handler_paginates_with_correct_limit_and_offset():
    """Test handler passes correct limit and offset to get_all_clients."""
    with patch(
        "wealth_management_portal_scheduler_tools.lambda_functions.get_client_list.ClientRepository"
    ) as mock_repo_cls:
        mock_repo_cls.return_value.get_all_clients.return_value = []

        lambda_handler({}, Mock())

        mock_repo_cls.return_value.get_all_clients.assert_called_once_with(limit=100, offset=0)


def test_handler_raises_on_redshift_error():
    """Test handler propagates exception when Redshift fails mid-pagination."""
    with patch(
        "wealth_management_portal_scheduler_tools.lambda_functions.get_client_list.ClientRepository"
    ) as mock_repo_cls:
        mock_repo_cls.return_value.get_all_clients.side_effect = Exception("Redshift connection failed")

        with pytest.raises(Exception, match="Redshift connection failed"):
            lambda_handler({}, Mock())


def test_handler_filters_null_client_ids():
    """Test handler skips clients with null client_id."""
    mock_clients = [
        {"client_id": "CLT-001"},
        {"client_id": None},
        {"client_id": "CLT-003"},
    ]

    with patch(
        "wealth_management_portal_scheduler_tools.lambda_functions.get_client_list.ClientRepository"
    ) as mock_repo_cls:
        mock_repo_cls.return_value.get_all_clients.return_value = mock_clients

        result = lambda_handler({}, Mock())

        assert result["count"] == 2
        assert "None" not in result["test_client_ids"]
