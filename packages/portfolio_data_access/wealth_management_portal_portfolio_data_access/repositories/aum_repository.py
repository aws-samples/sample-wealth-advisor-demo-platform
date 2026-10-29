"""Repository for advisor AUM data."""

import os

from .data_api_base_repository import DataApiBaseRepository


class AUMRepository(DataApiBaseRepository):
    """Repository for AUM trend data."""

    def get_total_aum_trends(self, limit: int = 12) -> list[dict]:
        """Get aggregated total AUM trends across all advisors."""
        if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
            sql = """
                SELECT
                    CAST(date_trunc('month', p.period_end_date) AS varchar) AS report_month,
                    sum(p.ending_value) AS total_aum
                FROM performance p
                JOIN portfolios pf ON CAST(p.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
                JOIN accounts acc ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
                JOIN clients c ON CAST(acc.client_id AS varchar) = CAST(c.client_id AS varchar)
                GROUP BY date_trunc('month', p.period_end_date)
                ORDER BY report_month DESC
                LIMIT :limit
            """
        else:
            sql = """
                SELECT report_month, SUM(total_aum) as total_aum
                FROM public.advisor_monthly_aum
                GROUP BY report_month
                ORDER BY report_month DESC
                LIMIT :limit
            """
        return self._execute_and_wait(sql, [{"name": "limit", "value": str(limit)}])

    def get_dashboard_summary(self) -> dict:
        """Get dashboard summary."""
        if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
            sql = """
                SELECT
                    COALESCE(sum(p_latest.ending_value), 0) AS total_aum_latest_month,
                    COALESCE(sum(p_prev.ending_value), 0) AS total_aum_previous_month,
                    COALESCE(sum(p_latest.ending_value), 0) - COALESCE(sum(p_prev.ending_value), 0) AS aum_change,
                    CASE WHEN COALESCE(sum(p_prev.ending_value), 0) > 0
                        THEN CAST(
                            (COALESCE(sum(p_latest.ending_value), 0)
                             - sum(p_prev.ending_value))
                            * 100.0 / sum(p_prev.ending_value)
                            AS decimal(10,2))
                        ELSE 0 END AS aum_change_pct,
                    COALESCE(avg(lp.time_weighted_return), 0)
                        AS avg_portfolio_return_pct,
                    COALESCE(avg(lp.ending_value - lp.beginning_value), 0)
                        AS avg_portfolio_return_value,
                    COUNT(DISTINCT CASE
                        WHEN t.transaction_date >= date_add(
                            'month', -1,
                            (SELECT max(transaction_date) FROM transactions))
                        THEN t_acc.client_id END)
                        AS active_clients_latest_month,
                    0 AS active_clients_change,
                    COALESCE(sum(CASE
                        WHEN f.billing_date >= date_add(
                            'month', -1,
                            (SELECT max(billing_date) FROM fees))
                        THEN f.fee_amount ELSE 0 END), 0)
                        AS total_fees_latest_month,
                    0 AS fees_change
                FROM performance p_latest
                JOIN portfolios pf
                    ON CAST(p_latest.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
                JOIN accounts acc
                    ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
                LEFT JOIN performance p_prev
                    ON CAST(p_prev.portfolio_id AS varchar) = CAST(p_latest.portfolio_id AS varchar)
                    AND p_prev.period_end_date >= date_add('month', -2, (SELECT max(period_end_date) FROM performance))
                    AND p_prev.period_end_date < date_add('month', -1, (SELECT max(period_end_date) FROM performance))
                LEFT JOIN (
                    SELECT portfolio_id, time_weighted_return, beginning_value, ending_value,
                           row_number() OVER (PARTITION BY portfolio_id ORDER BY period_end_date DESC) AS rn
                    FROM performance
                ) lp ON CAST(lp.portfolio_id AS varchar) = CAST(p_latest.portfolio_id AS varchar) AND lp.rn = 1
                LEFT JOIN transactions t ON CAST(t.account_id AS varchar) = CAST(acc.account_id AS varchar)
                LEFT JOIN accounts t_acc ON CAST(t.account_id AS varchar) = CAST(t_acc.account_id AS varchar)
                LEFT JOIN fees f ON CAST(f.account_id AS varchar) = CAST(acc.account_id AS varchar)
                WHERE p_latest.period_end_date >= date_add('month', -1, (SELECT max(period_end_date) FROM performance))
            """
        else:
            sql = "SELECT * FROM public.advisor_dashboard_summary LIMIT 1"
        results = self._execute_and_wait(sql)
        return results[0] if results else {}

    def get_client_aum(self, client_id: str, months: int = 12) -> list[dict]:
        """Get AUM data for a client."""
        if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
            sql = """
                SELECT
                    date_format(date_trunc('month', p.period_end_date), '%Y-%m') AS month,
                    sum(p.ending_value) AS aum_value
                FROM performance p
                JOIN portfolios pf ON CAST(p.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
                JOIN accounts acc ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
                WHERE CAST(acc.client_id AS varchar) = :client_id
                GROUP BY date_trunc('month', p.period_end_date)
                ORDER BY month DESC
                LIMIT :months
            """
        else:
            sql = """
                SELECT
                    TO_CHAR(report_month, 'YYYY-MM') as month,
                    total_aum as aum_value
                FROM investor_monthly_aum
                WHERE client_id = :client_id
                ORDER BY report_month DESC
                LIMIT :months
            """
        parameters = [{"name": "client_id", "value": client_id}, {"name": "months", "value": str(months)}]
        return self._execute_and_wait(sql, parameters)
