"""Repository for client segment data."""

import os

from .data_api_base_repository import DataApiBaseRepository


class ClientSegmentRepository(DataApiBaseRepository):
    """Repository for client segment data."""

    def get_client_segments(self) -> list[dict]:
        """Get client counts grouped by segment."""
        if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
            sql = """
                SELECT segment, COUNT(*) as client_count
                FROM clients
                WHERE segment IS NOT NULL AND segment != ''
                  AND status = 'Active'
                GROUP BY segment
                ORDER BY client_count DESC
            """
        else:
            sql = """
                SELECT segment, COUNT(*) as client_count
                FROM public.client_search
                WHERE segment IS NOT NULL AND segment != ''
                GROUP BY segment
                ORDER BY client_count DESC
            """
        return self._execute_and_wait(sql)
