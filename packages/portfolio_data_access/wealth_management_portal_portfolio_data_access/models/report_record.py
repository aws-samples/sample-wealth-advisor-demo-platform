# Redshift-mirroring model for client reports
from datetime import datetime

from pydantic import BaseModel


class ClientReport(BaseModel):
    """Report record from Redshift client_reports table."""

    report_id: str
    client_id: str
    # Null until report generation completes
    s3_path: str | None = None
    generated_date: datetime
    download_date: datetime | None = None
    status: str = "init"
    # AI-generated advisor recommendation; null until first nightly run
    next_best_action: str | None = None
