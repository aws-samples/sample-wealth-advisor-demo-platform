"""Repository for fetching all client report data from Redshift views."""

from collections.abc import Callable

from wealth_management_portal_portfolio_data_access.models.performance import PerformanceRecord
from wealth_management_portal_portfolio_data_access.models.portfolio import PortfolioRecord
from wealth_management_portal_portfolio_data_access.models.transaction import Transaction


class ClientReportRepository:
    """Queries client-scoped Redshift views to fetch report data."""

    def __init__(self, conn_factory: Callable):
        self._conn_factory = conn_factory

    def _execute(self, sql: str, params: list):
        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    def get_portfolios(self, client_id: str) -> list[PortfolioRecord]:
        # DISTINCT needed — merged view has one row per holding, not per portfolio
        sql = """
            SELECT DISTINCT portfolio_id, account_id, portfolio_name, investment_model,
                   target_allocation, benchmark, inception_date
            FROM public.client_portfolio_holdings
            WHERE client_id = %s
        """
        return [PortfolioRecord.model_validate(row) for row in self._execute(sql, [client_id])]

    def get_holdings_with_securities(self, client_id: str) -> list[dict]:
        sql = """
            SELECT portfolio_id, portfolio_name, position_id, security_id, quantity,
                   cost_basis, current_price, market_value, unrealized_gain_loss,
                   as_of_date, ticker, security_name, asset_class, sector
            FROM public.client_portfolio_holdings
            WHERE client_id = %s
        """
        return self._execute(sql, [client_id])

    def get_performance(self, client_id: str) -> list[PerformanceRecord]:
        sql = """
            SELECT performance_id, portfolio_id, period, period_start_date,
                   period_end_date, time_weighted_return, benchmark_return,
                   beginning_value, ending_value
            FROM public.client_portfolio_performance
            WHERE client_id = %s
            ORDER BY period_start_date
        """
        return [PerformanceRecord.model_validate(row) for row in self._execute(sql, [client_id])]

    def get_transactions(self, client_id: str) -> list[Transaction]:
        sql = """
            SELECT transaction_id, account_id, security_id, transaction_type,
                   transaction_date, settlement_date, quantity, price, amount, status
            FROM public.client_account_transactions
            WHERE client_id = %s
            ORDER BY transaction_date
        """
        return [Transaction.model_validate(row) for row in self._execute(sql, [client_id])]
