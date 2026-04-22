# Extended repository with write operations for report tracking
from collections.abc import Callable
from datetime import datetime

from wealth_management_portal_portfolio_data_access.models.report_record import ClientReport
from wealth_management_portal_portfolio_data_access.repositories.base import BaseRepository


class ReportRepository(BaseRepository[ClientReport]):
    """Report repository with save and update operations."""

    def __init__(self, conn_factory: Callable):
        super().__init__(
            conn_factory,
            ClientReport,
            "public.client_reports",
            {"report_id", "client_id", "s3_path", "generated_date", "download_date", "status", "next_best_action"},
        )
        self._conn_factory = conn_factory

    def save(self, report: ClientReport) -> None:
        """Insert a new report record."""
        sql = """
            INSERT INTO public.client_reports
                (report_id, client_id, s3_path, generated_date,
                 download_date, status, next_best_action)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    [
                        report.report_id,
                        report.client_id,
                        report.s3_path,
                        report.generated_date,
                        report.download_date,
                        report.status,
                        report.next_best_action,
                    ],
                )
            conn.commit()

    def update_download_date(self, report_id: str, download_date: datetime) -> None:
        """Update the download timestamp for a report."""
        sql = "UPDATE public.client_reports SET download_date = %s WHERE report_id = %s"
        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, [download_date, report_id])
            conn.commit()

    def update_status(self, report_id: str, status: str, s3_path: str | None = None) -> None:
        """Update the status and optionally s3_path for a report."""
        if s3_path is not None:
            sql = "UPDATE public.client_reports SET status = %s, s3_path = %s WHERE report_id = %s"
            params = [status, s3_path, report_id]
        else:
            sql = "UPDATE public.client_reports SET status = %s WHERE report_id = %s"
            params = [status, report_id]

        with self._conn_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()

    def get_latest_by_client(self, client_id: str) -> ClientReport | None:
        """Get the most recent report for a client."""
        sql = """
            SELECT * FROM public.client_reports 
            WHERE client_id = %s 
            ORDER BY generated_date DESC 
            LIMIT 1
        """
        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql, [client_id])
            rows = cur.fetchall()
            if not rows:
                return None

            # Build dict from cursor description and row data
            columns = [desc[0] for desc in cur.description]
            row_dict = dict(zip(columns, rows[0], strict=True))
            return ClientReport(**row_dict)
