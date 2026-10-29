"""Repository for holdings data."""

import os

from .data_api_base_repository import DataApiBaseRepository


class HoldingsRepository(DataApiBaseRepository):
    """Repository for holdings data."""

    def get_client_holdings(self, client_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
        """Get holdings for a specific client."""
        if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
            sql = """
                SELECT
                    h.portfolio_id,
                    s.security_id,
                    s.ticker,
                    s.security_name AS company_name,
                    h.quantity AS shares,
                    h.cost_basis,
                    h.current_price,
                    h.market_value AS current_value,
                    h.unrealized_gain_loss,
                    CAST(h.as_of_date AS varchar) AS as_of_date
                FROM holdings h
                JOIN portfolios pf ON CAST(h.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
                JOIN accounts acc ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
                LEFT JOIN securities s ON CAST(h.security_id AS varchar) = CAST(s.security_id AS varchar)
                WHERE CAST(acc.client_id AS varchar) = :client_id
                ORDER BY h.market_value DESC
                OFFSET :offset
                LIMIT :limit
            """
        else:
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
