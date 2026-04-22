"""Repository for client data."""

from .data_api_base_repository import DataApiBaseRepository


class ClientRepository(DataApiBaseRepository):
    """Repository for client data using Redshift Data API."""

    def get_all_clients(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Get all clients from client_search view."""
        sql = """
            SELECT
                client_id,
                client_first_name,
                client_last_name,
                segment AS client_segment,
                risk_tolerance,
                client_since AS client_created_date,
                aum,
                net_worth AS total_current_value,
                goals_on_track,
                ytd_performance AS time_weighted_return,
                interaction_sentiment,
                next_best_action
            FROM public.client_search
            ORDER BY client_id
            LIMIT :limit
            OFFSET :offset
        """
        parameters = [{"name": "limit", "value": str(limit)}, {"name": "offset", "value": str(offset)}]
        return self._execute_and_wait(sql, parameters)
