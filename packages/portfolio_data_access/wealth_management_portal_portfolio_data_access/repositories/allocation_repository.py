"""Repository for allocation data."""

import os

from .data_api_base_repository import DataApiBaseRepository


class AllocationRepository(DataApiBaseRepository):
    """Repository for allocation data using Redshift Data API."""

    def get_client_allocation(self, client_id: str) -> list[dict]:
        """Get target allocation for a client."""
        if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
            sql = (
                "SELECT p.target_allocation FROM portfolios AS p "
                "JOIN accounts AS a ON p.account_id = a.account_id "
                "WHERE a.client_id = :client_id LIMIT 1"
            )
        else:
            sql = "SELECT target_allocation FROM advisor_master WHERE client_id = :client_id LIMIT 1"
        return self._execute_and_wait(sql, [{"name": "client_id", "value": client_id}])
