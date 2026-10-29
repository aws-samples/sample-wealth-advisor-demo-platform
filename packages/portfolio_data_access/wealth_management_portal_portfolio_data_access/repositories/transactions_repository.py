"""Repository for transactions data."""

import os

from .data_api_base_repository import DataApiBaseRepository


class TransactionsRepository(DataApiBaseRepository):
    """Repository for transactions data."""

    def get_client_transactions(self, client_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
        """Get transactions for a specific client."""
        if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
            sql = """
                SELECT
                    t.transaction_id,
                    t.account_id,
                    t.security_id,
                    s.ticker,
                    t.transaction_type,
                    CAST(t.transaction_date AS varchar) AS transaction_date,
                    CAST(t.settlement_date AS varchar) AS settlement_date,
                    t.quantity,
                    t.price,
                    t.amount,
                    t.status
                FROM transactions t
                JOIN accounts acc ON CAST(t.account_id AS varchar) = CAST(acc.account_id AS varchar)
                LEFT JOIN securities s ON CAST(t.security_id AS varchar) = CAST(s.security_id AS varchar)
                WHERE CAST(acc.client_id AS varchar) = :client_id
                ORDER BY t.transaction_date DESC
                OFFSET :offset
                LIMIT :limit
            """
        else:
            sql = """
                SELECT
                    t.transaction_id,
                    t.account_id,
                    t.security_id,
                    s.ticker,
                    t.transaction_type,
                    t.transaction_date,
                    t.settlement_date,
                    t.quantity,
                    t.price,
                    t.amount,
                    t.status
                FROM public.client_account_transactions t
                LEFT JOIN "financial-advisor-s3table@s3tablescatalog"."financial_advisor"."securities" s
                    ON t.security_id = s.security_id
                WHERE t.client_id = :client_id
                ORDER BY t.transaction_date DESC
                LIMIT :limit OFFSET :offset
            """
        parameters = [
            {"name": "client_id", "value": client_id},
            {"name": "limit", "value": str(limit)},
            {"name": "offset", "value": str(offset)},
        ]
        return self._execute_and_wait(sql, parameters)
