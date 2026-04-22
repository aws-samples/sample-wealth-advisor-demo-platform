"""Handler for transactions endpoint."""

from pydantic import BaseModel
from wealth_management_portal_portfolio_data_access.repositories.transactions_repository import (
    TransactionsRepository,
)

from .init import logger


class TransactionResponse(BaseModel):
    """Response model for transaction data."""

    transaction_id: str
    account_id: str
    security_id: str | None
    ticker: str | None
    transaction_type: str
    transaction_date: str
    settlement_date: str | None
    quantity: float | None
    price: float | None
    amount: float | None
    status: str


class TransactionsListResponse(BaseModel):
    """Response model for transactions list."""

    transactions: list[TransactionResponse]


def get_client_transactions(client_id: str, limit: int = 20, offset: int = 0) -> TransactionsListResponse:
    """Get transactions for a specific client from Redshift."""
    try:
        logger.info("Fetching transactions for client: %s", client_id)
        repo = TransactionsRepository()

        transactions_data = repo.get_client_transactions(client_id, limit, offset)
        logger.info("Got %d transactions", len(transactions_data))

        transactions = []
        for txn in transactions_data:
            transactions.append(
                TransactionResponse(
                    transaction_id=str(txn.get("transaction_id", "")),
                    account_id=str(txn.get("account_id", "")),
                    security_id=(str(txn.get("security_id")) if txn.get("security_id") else None),
                    ticker=str(txn.get("ticker")) if txn.get("ticker") else None,
                    transaction_type=str(txn.get("transaction_type", "")),
                    transaction_date=str(txn.get("transaction_date", "")),
                    settlement_date=(str(txn.get("settlement_date")) if txn.get("settlement_date") else None),
                    quantity=(float(txn.get("quantity")) if txn.get("quantity") is not None else None),
                    price=(float(txn.get("price")) if txn.get("price") is not None else None),
                    amount=(float(txn.get("amount")) if txn.get("amount") is not None else None),
                    status=str(txn.get("status", "")),
                )
            )

        return TransactionsListResponse(transactions=transactions)

    except Exception:
        logger.exception("Error fetching transactions")
        return TransactionsListResponse(transactions=[])
