"""Repository for client details data."""

import os

from .data_api_base_repository import DataApiBaseRepository


class ClientDetailsRepository(DataApiBaseRepository):
    """Repository for client details data."""

    def get_client_details(self, client_id: str) -> dict:
        """Get complete client details."""
        if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
            sql = """
                SELECT
                    c.client_id,
                    concat(c.first_name, ' ', c.last_name) AS customer_name,
                    c.email,
                    c.phone,
                    c.segment,
                    c.risk_tolerance,
                    COALESCE(aum.total_aum, 0) AS total_current_value,
                    i.sentiment AS interaction_sentiment,
                    c.city AS client_city,
                    c.state AS client_state,
                    CAST(c.created_date AS varchar) AS client_created_date
                FROM clients c
                LEFT JOIN (
                    SELECT acc.client_id, sum(p.ending_value) AS total_aum
                    FROM performance p
                    JOIN portfolios pf ON CAST(p.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
                    JOIN accounts acc ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
                    WHERE p.period_end_date = (SELECT max(period_end_date) FROM performance)
                    GROUP BY acc.client_id
                ) aum ON CAST(c.client_id AS varchar) = CAST(aum.client_id AS varchar)
                LEFT JOIN (
                    SELECT client_id, sentiment,
                           row_number() OVER (PARTITION BY client_id ORDER BY interaction_date DESC) AS rn
                    FROM interactions
                ) i ON CAST(c.client_id AS varchar) = CAST(i.client_id AS varchar) AND i.rn = 1
                WHERE CAST(c.client_id AS varchar) = :client_id
                LIMIT 1
            """
        else:
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
