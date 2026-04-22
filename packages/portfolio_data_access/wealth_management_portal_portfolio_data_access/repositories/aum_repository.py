"""Repository for advisor AUM data."""

from .data_api_base_repository import DataApiBaseRepository


class AUMRepository(DataApiBaseRepository):
    """Repository for AUM trend data using Redshift Data API."""

    def get_total_aum_trends(self, limit: int = 12) -> list[dict]:
        """Get aggregated total AUM trends across all advisors."""
        sql = """
            SELECT report_month, SUM(total_aum) as total_aum
            FROM public.advisor_monthly_aum
            GROUP BY report_month
            ORDER BY report_month DESC
            LIMIT :limit
        """
        return self._execute_and_wait(sql, [{"name": "limit", "value": str(limit)}])

    def get_dashboard_summary(self) -> dict:
        """Get dashboard summary from advisor_dashboard_summary view."""
        sql = "SELECT * FROM public.advisor_dashboard_summary LIMIT 1"
        results = self._execute_and_wait(sql)
        return results[0] if results else {}

    def get_client_aum(self, client_id: str, months: int = 12) -> list[dict]:
        """Get AUM data for a client from investor_monthly_aum."""
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
