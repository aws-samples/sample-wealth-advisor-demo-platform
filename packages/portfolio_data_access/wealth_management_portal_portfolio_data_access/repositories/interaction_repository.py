# Extended repository for ordered/limited interaction queries
from collections.abc import Callable

from wealth_management_portal_portfolio_data_access.models.interaction import Interaction
from wealth_management_portal_portfolio_data_access.repositories.base import BaseRepository


class InteractionRepository(BaseRepository[Interaction]):
    """Interaction repository with ordering and limit support."""

    def __init__(self, conn_factory: Callable):
        super().__init__(
            conn_factory,
            Interaction,
            "public.client_interactions",
            {
                "interaction_id",
                "client_id",
                "advisor_id",
                "interaction_type",
                "interaction_date",
                "subject",
                "summary",
                "sentiment",
                "duration_minutes",
            },
        )
        self._conn_factory = conn_factory

    def get_recent(self, client_id: str, limit: int = 10) -> list[Interaction]:
        """Get most recent interactions for a client."""
        sql = """
            SELECT * FROM public.client_interactions
            WHERE client_id = %s
            ORDER BY interaction_date DESC
            LIMIT %s
        """
        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql, [client_id, limit])
            cols = [d[0] for d in cur.description]
            return [self._model.model_validate(dict(zip(cols, row, strict=True))) for row in cur.fetchall()]
