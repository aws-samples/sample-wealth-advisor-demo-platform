"""Repository for transactions data."""

from .data_api_base_repository import DataApiBaseRepository


class TransactionsRepository(DataApiBaseRepository):
    """Repository for transactions data using Redshift Data API."""

    def get_client_transactions(self, client_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
        """Get transactions for a specific client."""
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
