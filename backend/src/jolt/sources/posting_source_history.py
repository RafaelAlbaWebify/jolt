"""Read-only per-Posting source provenance without exposing raw capture contents."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from jolt.database import ConfirmedDuplicateLink, PortalSourceObservation, Posting
from jolt.errors import JoltNotFoundError
from jolt.sources.source_identity_registry import list_posting_sources


class PostingSourceHistoryIdentity(BaseModel):
    portal: str
    source_job_id: str
    source_url: str
    first_seen_at: datetime
    last_seen_at: datetime


class PostingSourceHistoryObservation(BaseModel):
    portal: str
    source_job_id: str
    source_url: str
    capture_run_id: str
    capture_item_id: str
    source_document_id_at_capture: str | None
    artifact_sha256: str
    observed_at: datetime


class ConfirmedDuplicateReference(BaseModel):
    posting_id: str
    confirmed_at: datetime


class PostingSourceHistoryResponse(BaseModel):
    posting_id: str
    sources: list[PostingSourceHistoryIdentity]
    observations: list[PostingSourceHistoryObservation]
    total_observations: int
    confirmed_duplicates: list[ConfirmedDuplicateReference] = []
    truncated: bool


def get_posting_source_history(
    session: Session, posting_id: str, *, limit: int = 100
) -> PostingSourceHistoryResponse:
    """Return a bounded source audit; no write, eligibility inference or full raw evidence."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    if session.get(Posting, posting_id) is None:
        raise JoltNotFoundError("Posting not found")
    sources = [
        PostingSourceHistoryIdentity(
            portal=source.portal,
            source_job_id=source.source_job_id,
            source_url=source.source_url,
            first_seen_at=source.first_seen_at,
            last_seen_at=source.last_seen_at,
        )
        for source in list_posting_sources(session, posting_id)
    ]
    total = int(
        session.scalar(
            select(func.count(PortalSourceObservation.id)).where(
                PortalSourceObservation.posting_id_at_capture == posting_id
            )
        )
        or 0
    )
    receipts = session.scalars(
        select(PortalSourceObservation)
        .where(PortalSourceObservation.posting_id_at_capture == posting_id)
        .order_by(PortalSourceObservation.observed_at, PortalSourceObservation.id)
        .limit(limit)
    ).all()
    observations = [
        PostingSourceHistoryObservation(
            portal=item.portal,
            source_job_id=item.source_job_id,
            source_url=item.source_url,
            capture_run_id=item.capture_run_id,
            capture_item_id=item.capture_item_id,
            source_document_id_at_capture=item.source_document_id_at_capture,
            artifact_sha256=item.artifact_sha256,
            observed_at=item.observed_at,
        )
        for item in receipts
    ]
    links = session.scalars(
        select(ConfirmedDuplicateLink)
        .where(
            or_(
                ConfirmedDuplicateLink.first_posting_id == posting_id,
                ConfirmedDuplicateLink.second_posting_id == posting_id,
            )
        )
        .order_by(ConfirmedDuplicateLink.confirmed_at)
    ).all()
    duplicates = [
        ConfirmedDuplicateReference(
            posting_id=(
                link.second_posting_id
                if link.first_posting_id == posting_id
                else link.first_posting_id
            ),
            confirmed_at=link.confirmed_at,
        )
        for link in links
    ]
    return PostingSourceHistoryResponse(
        confirmed_duplicates=duplicates,
        posting_id=posting_id,
        sources=sources,
        observations=observations,
        total_observations=total,
        truncated=total > limit,
    )
