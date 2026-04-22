"""Repository for holdings data."""

from .data_api_base_repository import DataApiBaseRepository


class HoldingsRepository(DataApiBaseRepository):
    """Repository for holdings data using Redshift Data API."""

    def get_client_holdings(self, client_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
        """Get holdings for a specific client from client_portfolio_holdings view."""
        sql = """
            SELECT 
                position_id,
                portfolio_id,
                security_id,
                ticker,
                security_name as company_name,
                quantity as shares,
                cost_basis,
                current_price,
                market_value as current_value,
                unrealized_gain_loss,
                as_of_date
            FROM public.client_portfolio_holdings
            WHERE client_id = :client_id
            ORDER BY market_value DESC
            LIMIT :limit OFFSET :offset
        """
        parameters = [
            {"name": "client_id", "value": client_id},
            {"name": "limit", "value": str(limit)},
            {"name": "offset", "value": str(offset)},
        ]
        return self._execute_and_wait(sql, parameters)
