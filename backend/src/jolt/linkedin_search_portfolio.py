from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import (
    LinkedInDiscoveryBatch,
    LinkedInDiscoveryBatchSearch,
    LinkedInSavedSearch,
    utc_now,
)
from jolt.errors import JoltNotFoundError
from jolt.linkedin_source_urls import normalize_linkedin_search_url


class SavedLinkedInSearchRequest(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    search_url: str = Field(min_length=1, max_length=4000)
    notes: str = Field(default="", max_length=1000)
    enabled: bool = True
    max_jobs: int = Field(default=100, ge=1, le=100)
    max_pages: int = Field(default=10, ge=1, le=10)


class SavedLinkedInSearchResponse(BaseModel):
    id: str
    label: str
    search_url: str
    notes: str
    enabled: bool
    max_jobs: int
    max_pages: int
    created_at: datetime
    updated_at: datetime


class DiscoveryBatchCreateRequest(BaseModel):
    saved_search_ids: list[str] = Field(min_length=1, max_length=25)


class DiscoveryBatchSearchResponse(BaseModel):
    id: str
    saved_search_id: str
    position: int
    label: str
    search_url: str
    max_jobs: int
    max_pages: int
    status: str
    capture_run_id: str | None
    captured_count: int
    verified_count: int
    new_posting_count: int
    duplicate_count: int
    error: str
    started_at: datetime | None
    completed_at: datetime | None


class DiscoveryBatchResponse(BaseModel):
    id: str
    status: str
    selected_search_count: int
    completed_search_count: int
    failed_search_count: int
    captured_count: int
    verified_count: int
    new_posting_count: int
    duplicate_count: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    searches: list[DiscoveryBatchSearchResponse]


def _canonical_search_url(value: str) -> str:
    canonical = normalize_linkedin_search_url(value)
    parsed = urlsplit(canonical)
    if not parsed.netloc.casefold().endswith("linkedin.com"):
        raise ValueError("Saved search URL must be a LinkedIn URL.")
    if not parsed.path.startswith("/jobs/search"):
        raise ValueError("Saved search URL must point to LinkedIn job search results.")
    return canonical


def _saved_search_response(search: LinkedInSavedSearch) -> SavedLinkedInSearchResponse:
    return SavedLinkedInSearchResponse(
        id=search.id,
        label=search.label,
        search_url=search.search_url,
        notes=search.notes,
        enabled=search.enabled,
        max_jobs=search.max_jobs,
        max_pages=search.max_pages,
        created_at=search.created_at,
        updated_at=search.updated_at,
    )


def list_saved_linkedin_searches(session: Session) -> list[SavedLinkedInSearchResponse]:
    searches = session.scalars(
        select(LinkedInSavedSearch).order_by(
            LinkedInSavedSearch.created_at.asc(),
            LinkedInSavedSearch.id.asc(),
        )
    ).all()
    return [_saved_search_response(search) for search in searches]


def get_saved_linkedin_search(
    session: Session,
    saved_search_id: str,
) -> SavedLinkedInSearchResponse:
    search = session.get(LinkedInSavedSearch, saved_search_id)
    if search is None:
        raise JoltNotFoundError("Saved LinkedIn search was not found.")
    return _saved_search_response(search)


def _ensure_unique_canonical_url(
    session: Session,
    canonical_url: str,
    *,
    exclude_id: str | None = None,
) -> None:
    statement = select(LinkedInSavedSearch.id).where(
        LinkedInSavedSearch.search_url == canonical_url
    )
    if exclude_id is not None:
        statement = statement.where(LinkedInSavedSearch.id != exclude_id)
    if session.scalar(statement.limit(1)) is not None:
        raise ValueError("A saved LinkedIn search already uses these search criteria.")


def create_saved_linkedin_search(
    session: Session,
    request: SavedLinkedInSearchRequest,
) -> SavedLinkedInSearchResponse:
    if not request.label.strip():
        raise ValueError("Saved search label cannot be blank.")
    canonical_url = _canonical_search_url(request.search_url)
    _ensure_unique_canonical_url(session, canonical_url)
    now = utc_now()
    search = LinkedInSavedSearch(
        id=str(uuid4()),
        label=request.label.strip(),
        search_url=canonical_url,
        notes=request.notes.strip(),
        enabled=request.enabled,
        max_jobs=request.max_jobs,
        max_pages=request.max_pages,
        created_at=now,
        updated_at=now,
    )
    session.add(search)
    session.commit()
    return _saved_search_response(search)


def update_saved_linkedin_search(
    session: Session,
    saved_search_id: str,
    request: SavedLinkedInSearchRequest,
) -> SavedLinkedInSearchResponse:
    search = session.get(LinkedInSavedSearch, saved_search_id)
    if search is None:
        raise JoltNotFoundError("Saved LinkedIn search was not found.")
    if not request.label.strip():
        raise ValueError("Saved search label cannot be blank.")
    canonical_url = _canonical_search_url(request.search_url)
    _ensure_unique_canonical_url(session, canonical_url, exclude_id=search.id)
    search.label = request.label.strip()
    search.search_url = canonical_url
    search.notes = request.notes.strip()
    search.enabled = request.enabled
    search.max_jobs = request.max_jobs
    search.max_pages = request.max_pages
    search.updated_at = utc_now()
    session.commit()
    return _saved_search_response(search)


def delete_saved_linkedin_search(session: Session, saved_search_id: str) -> None:
    search = session.get(LinkedInSavedSearch, saved_search_id)
    if search is None:
        raise JoltNotFoundError("Saved LinkedIn search was not found.")
    historical_reference = session.scalar(
        select(LinkedInDiscoveryBatchSearch.id)
        .where(LinkedInDiscoveryBatchSearch.saved_search_id == saved_search_id)
        .limit(1)
    )
    if historical_reference is not None:
        raise ValueError(
            "Saved search is referenced by discovery history; disable it instead of deleting it."
        )
    session.delete(search)
    session.commit()


def _batch_search_response(
    search: LinkedInDiscoveryBatchSearch,
) -> DiscoveryBatchSearchResponse:
    return DiscoveryBatchSearchResponse(
        id=search.id,
        saved_search_id=search.saved_search_id,
        position=search.position,
        label=search.label_snapshot,
        search_url=search.search_url_snapshot,
        max_jobs=search.max_jobs_snapshot,
        max_pages=search.max_pages_snapshot,
        status=search.status,
        capture_run_id=search.capture_run_id,
        captured_count=search.captured_count,
        verified_count=search.verified_count,
        new_posting_count=search.new_posting_count,
        duplicate_count=search.duplicate_count,
        error=search.error,
        started_at=search.started_at,
        completed_at=search.completed_at,
    )


def get_discovery_batch(session: Session, batch_id: str) -> DiscoveryBatchResponse:
    batch = session.get(LinkedInDiscoveryBatch, batch_id)
    if batch is None:
        raise JoltNotFoundError("LinkedIn discovery batch was not found.")
    searches = session.scalars(
        select(LinkedInDiscoveryBatchSearch)
        .where(LinkedInDiscoveryBatchSearch.batch_id == batch.id)
        .order_by(LinkedInDiscoveryBatchSearch.position.asc())
    ).all()
    completed_search_count = sum(search.status == "completed" for search in searches)
    failed_search_count = sum(search.status == "failed" for search in searches)
    return DiscoveryBatchResponse(
        id=batch.id,
        status=batch.status,
        selected_search_count=batch.selected_search_count,
        completed_search_count=completed_search_count,
        failed_search_count=failed_search_count,
        captured_count=sum(search.captured_count for search in searches),
        verified_count=sum(search.verified_count for search in searches),
        new_posting_count=sum(search.new_posting_count for search in searches),
        duplicate_count=sum(search.duplicate_count for search in searches),
        started_at=batch.started_at,
        completed_at=batch.completed_at,
        created_at=batch.created_at,
        searches=[_batch_search_response(search) for search in searches],
    )


def list_discovery_batches(session: Session) -> list[DiscoveryBatchResponse]:
    batches = session.scalars(
        select(LinkedInDiscoveryBatch).order_by(
            LinkedInDiscoveryBatch.created_at.desc(),
            LinkedInDiscoveryBatch.id.desc(),
        )
    ).all()
    return [get_discovery_batch(session, batch.id) for batch in batches]


def create_discovery_batch(
    session: Session,
    request: DiscoveryBatchCreateRequest,
) -> DiscoveryBatchResponse:
    if len(request.saved_search_ids) != len(set(request.saved_search_ids)):
        raise ValueError("Discovery batch search IDs must be unique.")

    searches: list[LinkedInSavedSearch] = []
    for saved_search_id in request.saved_search_ids:
        search = session.get(LinkedInSavedSearch, saved_search_id)
        if search is None:
            raise JoltNotFoundError(f"Saved LinkedIn search was not found: {saved_search_id}")
        if not search.enabled:
            raise ValueError(f"Saved LinkedIn search is disabled: {search.label}")
        searches.append(search)

    now = utc_now()
    batch = LinkedInDiscoveryBatch(
        id=str(uuid4()),
        status="queued",
        selected_search_count=len(searches),
        started_at=None,
        completed_at=None,
        created_at=now,
    )
    session.add(batch)
    session.flush()

    for position, search in enumerate(searches, start=1):
        session.add(
            LinkedInDiscoveryBatchSearch(
                id=str(uuid4()),
                batch_id=batch.id,
                saved_search_id=search.id,
                position=position,
                label_snapshot=search.label,
                search_url_snapshot=search.search_url,
                max_jobs_snapshot=search.max_jobs,
                max_pages_snapshot=search.max_pages,
                status="queued",
                capture_run_id=None,
                captured_count=0,
                verified_count=0,
                new_posting_count=0,
                duplicate_count=0,
                error="",
                started_at=None,
                completed_at=None,
            )
        )

    session.commit()
    return get_discovery_batch(session, batch.id)
