from pydantic import BaseModel
from wealth_management_portal_portfolio_data_access.repositories.client_segment_repository import (
    ClientSegmentRepository,
)

from .init import logger


class ClientSegment(BaseModel):
    segment: str
    client_count: int
    percentage: float


class ClientSegmentsResponse(BaseModel):
    segments: list[ClientSegment]
    total_clients: int


def get_client_segments() -> ClientSegmentsResponse:
    """Get client segment distribution from advisor_master"""
    try:
        repo = ClientSegmentRepository()
        rows = repo.get_client_segments()

        logger.info("Got %d segments", len(rows))

        if not rows:
            return ClientSegmentsResponse(segments=[], total_clients=0)

        total_clients = sum(row["client_count"] for row in rows)

        segments = [
            ClientSegment(
                segment=row["segment"],
                client_count=row["client_count"],
                percentage=round((row["client_count"] / total_clients * 100), 2),
            )
            for row in rows
        ]

        return ClientSegmentsResponse(segments=segments, total_clients=total_clients)
    except Exception:
        logger.warning("Error in get_client_segments", exc_info=True)
        raise
