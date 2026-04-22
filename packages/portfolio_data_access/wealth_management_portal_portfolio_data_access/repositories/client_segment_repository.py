"""Repository for client segment data."""

from .data_api_base_repository import DataApiBaseRepository


class ClientSegmentRepository(DataApiBaseRepository):
    """Repository for client segment data using Redshift Data API."""

    def get_client_segments(self) -> list[dict]:
        """Get client counts grouped by segment."""
        sql = """
            SELECT segment, COUNT(*) as client_count 
            FROM public.client_search 
            WHERE segment IS NOT NULL AND segment != '' 
            GROUP BY segment 
            ORDER BY client_count DESC
        """
        return self._execute_and_wait(sql)
