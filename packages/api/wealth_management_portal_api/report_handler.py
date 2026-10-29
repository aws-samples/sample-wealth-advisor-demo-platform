"""Report handler — client report status, download, and on-demand generation."""

import json
import os
import uuid
from datetime import datetime, timedelta

import boto3
from aws_lambda_powertools import Logger
from fastapi import HTTPException
from pydantic import BaseModel

logger = Logger()

REPORT_S3_BUCKET = os.environ.get("REPORT_S3_BUCKET", "")
REPORT_AGENT_ARN = os.environ.get("REPORT_AGENT_ARN", "")
GENERATE_REPORT_LAMBDA_ARN = os.environ.get("GENERATE_REPORT_LAMBDA_ARN", "")
PENDING_TIMEOUT_MINUTES = 3


class ReportStatusResponse(BaseModel):
    """Response model for client report status."""

    report_id: str | None
    status: str
    presigned_url: str | None = None
    next_best_action: str | None = None


class ReportsSummaryResponse(BaseModel):
    """Summary of which clients have reports available."""

    clients_with_reports: list[str]


def get_reports_summary() -> ReportsSummaryResponse:
    """Return list of client IDs that have completed reports."""
    logger.info("Fetching reports summary")

    if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
        return _get_reports_summary_athena()

    return _get_reports_summary_redshift()


def _filter_existing_reports(candidates: list[tuple[str, str]]) -> list[str]:
    """Given (client_id, s3_path) candidates, return client_ids whose PDF exists in S3.

    A client counts as "report available" only when its PDF is present in S3 — a
    client_reports row with status='complete' is NOT sufficient (seed rows and
    NBA-only records point at s3_paths whose objects were never generated). Uses
    head_object (s3:GetObject) so it needs no extra ListBucket permission.
    """
    if not REPORT_S3_BUCKET:
        return []
    s3_client = boto3.client("s3")
    available: list[str] = []
    for client_id, s3_path in candidates:
        if not s3_path:
            continue
        try:
            s3_client.head_object(Bucket=REPORT_S3_BUCKET, Key=s3_path)
            available.append(client_id)
        except Exception:
            # Missing object (or any access issue) => not available; row shows Generate.
            pass
    return available


def _get_reports_summary_athena() -> ReportsSummaryResponse:
    from wealth_management_portal_portfolio_data_access.repositories.data_api_base_repository import (
        DataApiBaseRepository,
    )

    repo = DataApiBaseRepository()
    sql = """
        SELECT client_id, s3_path FROM (
            SELECT client_id, status, s3_path,
                   ROW_NUMBER() OVER (PARTITION BY client_id ORDER BY generated_date DESC) AS rn
            FROM client_reports
        ) latest
        WHERE rn = 1 AND status = 'complete' AND s3_path LIKE 'reports/%'
    """
    results = repo._execute_and_wait(sql)
    candidates = [(r["client_id"], r.get("s3_path")) for r in (results or [])]
    return ReportsSummaryResponse(clients_with_reports=_filter_existing_reports(candidates))


def _get_reports_summary_redshift() -> ReportsSummaryResponse:
    from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory

    factory = iam_connection_factory()
    with factory() as conn:
        cursor = conn.execute(
            """SELECT client_id, s3_path FROM (
                SELECT client_id, status, s3_path,
                       ROW_NUMBER() OVER (PARTITION BY client_id ORDER BY generated_date DESC) AS rn
                FROM public.client_reports
            ) latest
            WHERE rn = 1 AND status = 'complete' AND s3_path LIKE 'reports/%'"""
        )
        rows = cursor.fetchall()
    candidates = [(row[0], row[1]) for row in rows]
    return ReportsSummaryResponse(clients_with_reports=_filter_existing_reports(candidates))


def get_client_report(client_id: str) -> ReportStatusResponse:
    """Get latest report status and presigned download URL for a client."""
    logger.info("Fetching report for client", client_id=client_id)

    if os.environ.get("DATA_ENGINE", "athena").lower() == "athena":
        return _get_report_athena(client_id)

    return _get_report_redshift(client_id)


def generate_client_report(client_id: str) -> ReportStatusResponse:
    """Trigger async report generation: insert pending row, invoke Lambda, return immediately."""
    logger.info("Generating report for client", client_id=client_id)

    if not GENERATE_REPORT_LAMBDA_ARN and not REPORT_AGENT_ARN:
        logger.warning("Neither GENERATE_REPORT_LAMBDA_ARN nor REPORT_AGENT_ARN configured")
        return ReportStatusResponse(
            report_id=None,
            status="error",
            next_best_action="Report generation not configured",
        )

    report_id = f"RPT-{uuid.uuid4().hex[:10].upper()}"
    is_athena = os.environ.get("DATA_ENGINE", "athena").lower() == "athena"

    try:
        if is_athena:
            _insert_pending_report_athena(report_id, client_id)
        else:
            _insert_pending_report_redshift(report_id, client_id)
    except Exception:
        logger.exception("Failed to write pending report row", client_id=client_id)

    try:
        if GENERATE_REPORT_LAMBDA_ARN:
            lambda_client = boto3.client("lambda")
            lambda_client.invoke(
                FunctionName=GENERATE_REPORT_LAMBDA_ARN,
                InvocationType="Event",
                Payload=json.dumps({"client_id": client_id}).encode(),
            )
        else:
            lambda_client = boto3.client("lambda")
            lambda_client.invoke(
                FunctionName=os.environ.get("AWS_LAMBDA_FUNCTION_NAME", ""),
                InvocationType="Event",
                Payload=json.dumps({"_generate_report_sync": True, "client_id": client_id}).encode(),
            )
    except Exception as e:
        logger.exception("Failed to invoke report generation Lambda", client_id=client_id)
        return ReportStatusResponse(
            report_id=report_id,
            status="error",
            next_best_action=f"Failed to start generation: {str(e)[:100]}",
        )

    return ReportStatusResponse(report_id=report_id, status="pending")


def _save_report_to_athena(report_id: str, client_id: str, s3_path: str, next_best_action: str):
    """Write report record to S3 Tables via Athena INSERT INTO."""
    from wealth_management_portal_portfolio_data_access.repositories.data_api_base_repository import (
        DataApiBaseRepository,
    )

    repo = DataApiBaseRepository()
    safe_nba = next_best_action.replace("'", "''")[:500] if next_best_action else ""
    sql = f"""
        INSERT INTO client_reports (report_id, client_id, s3_path, status, generated_date, next_best_action)
        VALUES ('{report_id}', '{client_id}', '{s3_path}', 'complete', current_timestamp, '{safe_nba}')
    """
    try:
        repo._execute_and_wait(sql)
    except Exception:
        logger.warning("Failed to save report to Athena", exc_info=True)


def _update_status_athena(report_id: str, new_status: str):
    """Update an existing report row's status in the DB (best-effort, non-blocking)."""
    if not report_id:
        return
    try:
        from wealth_management_portal_portfolio_data_access.repositories.data_api_base_repository import (
            DataApiBaseRepository,
        )

        repo = DataApiBaseRepository()
        sql = f"UPDATE client_reports SET status = '{new_status}' WHERE report_id = '{report_id}'"
        repo._execute_and_wait(sql)
    except Exception:
        logger.debug("Failed to update report status", report_id=report_id, exc_info=True)


def _insert_pending_report_athena(report_id: str, client_id: str):
    """Write a pending row before async generation starts."""
    from wealth_management_portal_portfolio_data_access.repositories.data_api_base_repository import (
        DataApiBaseRepository,
    )

    repo = DataApiBaseRepository()
    sql = f"""
        INSERT INTO client_reports (report_id, client_id, s3_path, status, generated_date, next_best_action)
        VALUES ('{report_id}', '{client_id}', '', 'pending', current_timestamp, '')
    """
    repo._execute_and_wait(sql)


def _insert_pending_report_redshift(report_id: str, client_id: str):
    """Write a pending row via Redshift before async generation starts."""
    from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory

    factory = iam_connection_factory()
    with factory() as conn:
        conn.execute(
            "INSERT INTO public.client_reports (report_id, client_id, s3_path, status, generated_date) "
            "VALUES (%s, %s, '', 'pending', NOW())",
            (report_id, client_id),
        )


def _get_report_athena(client_id: str) -> ReportStatusResponse:
    """Fetch report status via Athena (S3 Tables)."""
    from wealth_management_portal_portfolio_data_access.repositories.data_api_base_repository import (
        DataApiBaseRepository,
    )

    repo = DataApiBaseRepository()
    sql = """
        SELECT report_id, client_id, s3_path, status, next_best_action,
               CAST(generated_date AS varchar) AS generated_date
        FROM client_reports
        WHERE client_id = :client_id
        ORDER BY generated_date DESC
        LIMIT 1
    """
    results = repo._execute_and_wait(sql, [{"name": "client_id", "value": client_id}])

    if not results:
        return ReportStatusResponse(report_id=None, status="not_found")

    report = results[0]
    presigned_url = None

    if report.get("status") == "complete" and report.get("s3_path") and REPORT_S3_BUCKET:
        try:
            s3_client = boto3.client("s3")
            s3_client.head_object(Bucket=REPORT_S3_BUCKET, Key=report["s3_path"])
            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": REPORT_S3_BUCKET, "Key": report["s3_path"]},
                ExpiresIn=3600,
            )
        except s3_client.exceptions.NoSuchKey:
            logger.info("Report file not found in S3", s3_path=report["s3_path"])
        except Exception as e:
            if "404" in str(e) or "Not Found" in str(e):
                logger.info("Report file not found in S3", s3_path=report["s3_path"])
            else:
                logger.error("Failed to generate presigned URL", error=str(e))
                raise HTTPException(status_code=500, detail="Failed to generate download URL") from e

    effective_status = report.get("status", "unknown")
    if effective_status == "complete" and presigned_url is None:
        # Report-only, never persisted: a missing S3 object is not proof the row is bad
        # (wrong/rotated bucket looks identical). Writing it back rewrote seed rows on
        # every page view, and Iceberg compaction then made the deletes permanent.
        effective_status = "file_missing"

    if effective_status == "pending":
        generated_date_str = report.get("generated_date", "")
        if generated_date_str:
            try:
                generated_date = datetime.fromisoformat(str(generated_date_str).replace(" ", "T").split(".")[0])
                if datetime.now() - generated_date > timedelta(minutes=PENDING_TIMEOUT_MINUTES):
                    effective_status = "error"
                    _update_status_athena(report.get("report_id", ""), "error")
            except (ValueError, TypeError):
                pass

    return ReportStatusResponse(
        report_id=report.get("report_id"),
        status=effective_status,
        presigned_url=presigned_url,
        next_best_action=report.get("next_best_action"),
    )


def _get_report_redshift(client_id: str) -> ReportStatusResponse:
    """Fetch report status via direct Redshift connection."""
    from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory
    from wealth_management_portal_portfolio_data_access.repositories.report_repository import (
        ReportRepository,
    )

    repo = ReportRepository(iam_connection_factory())
    report = repo.get_latest_by_client(client_id)

    if not report:
        return ReportStatusResponse(report_id=None, status="not_found")

    presigned_url = None
    if report.status == "complete" and report.s3_path:
        try:
            s3_client = boto3.client("s3")
            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": REPORT_S3_BUCKET, "Key": report.s3_path},
                ExpiresIn=3600,
            )
        except Exception as e:
            logger.error("Failed to generate presigned URL", report_id=report.report_id, error=str(e))
            raise HTTPException(status_code=500, detail="Failed to generate download URL") from e

    status = report.status
    if status == "pending" and report.generated_date:
        try:
            if datetime.now() - report.generated_date > timedelta(minutes=PENDING_TIMEOUT_MINUTES):
                status = "error"
        except (ValueError, TypeError):
            pass

    return ReportStatusResponse(
        report_id=report.report_id,
        status=status,
        presigned_url=presigned_url,
        next_best_action=report.next_best_action,
    )
