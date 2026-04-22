"""Repository for advisor-related data access."""

from .data_api_base_repository import DataApiBaseRepository


class AdvisorRepository(DataApiBaseRepository):
    """Repository for advisor data operations."""

    def get_top_clients(self, limit: int = 5) -> list[dict]:
        """Get top clients by net worth from advisor_master view."""
        sql = """
            SELECT DISTINCT
                client_id,
                client_first_name,
                client_last_name,
                total_current_value,
                ytd_return_pct
            FROM public.advisor_master
            WHERE total_current_value IS NOT NULL
            ORDER BY total_current_value DESC
            LIMIT :limit
        """
        return self._execute_and_wait(sql, [{"name": "limit", "value": str(limit)}])
