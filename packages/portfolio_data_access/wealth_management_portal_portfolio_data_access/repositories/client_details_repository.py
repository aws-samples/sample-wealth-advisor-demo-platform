"""Repository for client details data."""

from .data_api_base_repository import DataApiBaseRepository


class ClientDetailsRepository(DataApiBaseRepository):
    """Repository for client details data using Redshift Data API."""

    def get_client_details(self, client_id: str) -> dict:
        """Get complete client details."""
        sql = """
            SELECT 
                client_id,
                client_name as customer_name,
                email,
                phone,
                segment,
                risk_tolerance,
                aum as total_current_value,
                interaction_sentiment,
                city as client_city,
                state as client_state,
                client_since as client_created_date
            FROM public.client_search
            WHERE client_id = :client_id
            LIMIT 1
        """
        results = self._execute_and_wait(sql, [{"name": "client_id", "value": client_id}])
        return results[0] if results else {}
