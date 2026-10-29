"""Repository for client data."""

import os

from .data_api_base_repository import DataApiBaseRepository


class ClientRepository(DataApiBaseRepository):
    """Repository for client data."""

    def get_all_clients(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Get all clients."""
        if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
            sql = """
                SELECT
                    c.client_id,
                    c.first_name AS client_first_name,
                    c.last_name AS client_last_name,
                    c.segment AS client_segment,
                    c.risk_tolerance,
                    CAST(c.created_date AS varchar) AS client_created_date,
                    COALESCE(aum.total_aum, 0) AS aum,
                    COALESCE(aum.total_aum, 0) AS total_current_value,
                    NULL AS goals_on_track,
                    COALESCE(perf.ytd_return, 0) AS time_weighted_return,
                    i.sentiment AS interaction_sentiment,
                    cr.next_best_action
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
                    SELECT acc.client_id, avg(p.time_weighted_return) AS ytd_return
                    FROM performance p
                    JOIN portfolios pf ON CAST(p.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
                    JOIN accounts acc ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
                    WHERE p.period_end_date >= date_trunc('year', current_date)
                    GROUP BY acc.client_id
                ) perf ON CAST(c.client_id AS varchar) = CAST(perf.client_id AS varchar)
                LEFT JOIN (
                    SELECT client_id, sentiment,
                           row_number() OVER (PARTITION BY client_id ORDER BY interaction_date DESC) AS rn
                    FROM interactions
                ) i ON CAST(c.client_id AS varchar) = CAST(i.client_id AS varchar) AND i.rn = 1
                LEFT JOIN (
                    SELECT client_id, next_best_action,
                           row_number() OVER (PARTITION BY client_id ORDER BY generated_date DESC) AS rn
                    FROM client_reports
                    WHERE next_best_action IS NOT NULL AND next_best_action <> ''
                ) cr ON CAST(c.client_id AS varchar) = CAST(cr.client_id AS varchar) AND cr.rn = 1
                WHERE c.status = 'Active'
                ORDER BY c.client_id
                OFFSET :offset
                LIMIT :limit
            """
        else:
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
