from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import DiscoverySavedSearch, LinkedInSavedSearch, utc_now
from jolt.errors import JoltNotFoundError

DiscoverySource = Literal["linkedin", "indeed", "jobgether", "infojobs", "adzuna"]

_SOURCE_CAPABILITIES: dict[str, dict[str, Any]] = {
    "linkedin": {
        "label": "LinkedIn",
        "transport": "browser",
        "saved_search_backend": "legacy_linkedin",
        "execution_available": True,
    },
    "indeed": {
        "label": "Indeed",
        "transport": "browser",
        "saved_search_backend": "discovery",
        "execution_available": True,
    },
    "jobgether": {
        "label": "Jobgether",
        "transport": "api",
        "saved_search_backend": "discovery",
        "execution_available": False,
    },
    "infojobs": {
        "label": "InfoJobs",
        "transport": "api",
        "saved_search_backend": "discovery",
        "execution_available": False,
    },
    "adzuna": {
        "label": "Adzuna",
        "transport": "api",
        "saved_search_backend": "discovery",
        "execution_available": False,
    },
}


class DiscoverySourceResponse(BaseModel):
    source: DiscoverySource
    label: str
    transport: Literal["api", "browser"]
    saved_search_backend: str
    execution_available: bool


class DiscoverySavedSearchRequest(BaseModel):
    source: DiscoverySource
    label: str = Field(min_length=1, max_length=200)
    definition: dict[str, Any]
    notes: str = Field(default="", max_length=1000)
    enabled: bool = True
    max_jobs: int = Field(default=50, ge=1, le=100)


class DiscoverySavedSearchResponse(BaseModel):
    id: str
    source: DiscoverySource
    label: str
    definition: dict[str, Any]
    notes: str
    enabled: bool
    max_jobs: int
    created_at: datetime
    updated_at: datetime
    execution_available: bool


def list_discovery_sources() -> list[DiscoverySourceResponse]:
    return [
        DiscoverySourceResponse(source=cast(DiscoverySource, source), **capabilities)
        for source, capabilities in _SOURCE_CAPABILITIES.items()
    ]


def _canonical_definition(definition: dict[str, Any]) -> tuple[str, str]:
    serialized = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    key = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return serialized, key


def _validate_non_linkedin(request: DiscoverySavedSearchRequest) -> None:
    if request.source == "linkedin":
        raise ValueError(
            "LinkedIn saved searches remain managed by the existing LinkedIn search editor during the migration to multi-source discovery."
        )
    if not request.label.strip():
        raise ValueError("Saved search label cannot be blank.")
    if not request.definition:
        raise ValueError("Saved search definition cannot be empty.")


def _response(search: DiscoverySavedSearch) -> DiscoverySavedSearchResponse:
    source = cast(DiscoverySource, search.source)
    capabilities = _SOURCE_CAPABILITIES.get(source, {})
    return DiscoverySavedSearchResponse(
        id=search.id,
        source=source,
        label=search.label,
        definition=json.loads(search.definition_json),
        notes=search.notes,
        enabled=search.enabled,
        max_jobs=search.max_jobs,
        created_at=search.created_at,
        updated_at=search.updated_at,
        execution_available=bool(capabilities.get("execution_available", False)),
    )


def _linkedin_response(search: LinkedInSavedSearch) -> DiscoverySavedSearchResponse:
    return DiscoverySavedSearchResponse(
        id=search.id,
        source="linkedin",
        label=search.label,
        definition={
            "search_url": search.search_url,
            "max_pages": search.max_pages,
        },
        notes=search.notes,
        enabled=search.enabled,
        max_jobs=search.max_jobs,
        created_at=search.created_at,
        updated_at=search.updated_at,
        execution_available=True,
    )


def list_discovery_searches(
    session: Session,
    *,
    source: DiscoverySource | None = None,
) -> list[DiscoverySavedSearchResponse]:
    results: list[DiscoverySavedSearchResponse] = []
    if source in {None, "linkedin"}:
        linkedin = session.scalars(
            select(LinkedInSavedSearch).order_by(
                LinkedInSavedSearch.created_at.asc(),
                LinkedInSavedSearch.id.asc(),
            )
        ).all()
        results.extend(_linkedin_response(item) for item in linkedin)

    if source != "linkedin":
        statement = select(DiscoverySavedSearch)
        if source is not None:
            statement = statement.where(DiscoverySavedSearch.source == source)
        generic = session.scalars(
            statement.order_by(
                DiscoverySavedSearch.created_at.asc(),
                DiscoverySavedSearch.id.asc(),
            )
        ).all()
        results.extend(_response(item) for item in generic)

    return results


def create_discovery_search(
    session: Session,
    request: DiscoverySavedSearchRequest,
) -> DiscoverySavedSearchResponse:
    _validate_non_linkedin(request)
    definition_json, definition_key = _canonical_definition(request.definition)
    existing = session.scalar(
        select(DiscoverySavedSearch.id)
        .where(
            DiscoverySavedSearch.source == request.source,
            DiscoverySavedSearch.definition_key == definition_key,
        )
        .limit(1)
    )
    if existing is not None:
        raise ValueError("A saved search already uses this portal and search definition.")

    now = utc_now()
    search = DiscoverySavedSearch(
        id=str(uuid4()),
        source=request.source,
        label=request.label.strip(),
        definition_json=definition_json,
        definition_key=definition_key,
        notes=request.notes.strip(),
        enabled=request.enabled,
        max_jobs=request.max_jobs,
        created_at=now,
        updated_at=now,
    )
    session.add(search)
    session.commit()
    return _response(search)


def update_discovery_search(
    session: Session,
    saved_search_id: str,
    request: DiscoverySavedSearchRequest,
) -> DiscoverySavedSearchResponse:
    _validate_non_linkedin(request)
    search = session.get(DiscoverySavedSearch, saved_search_id)
    if search is None:
        raise JoltNotFoundError("Saved discovery search was not found.")
    if search.source != request.source:
        raise ValueError(
            "A saved search cannot be moved to another portal; create a new search instead."
        )

    definition_json, definition_key = _canonical_definition(request.definition)
    existing = session.scalar(
        select(DiscoverySavedSearch.id)
        .where(
            DiscoverySavedSearch.source == request.source,
            DiscoverySavedSearch.definition_key == definition_key,
            DiscoverySavedSearch.id != saved_search_id,
        )
        .limit(1)
    )
    if existing is not None:
        raise ValueError("A saved search already uses this portal and search definition.")

    search.label = request.label.strip()
    search.definition_json = definition_json
    search.definition_key = definition_key
    search.notes = request.notes.strip()
    search.enabled = request.enabled
    search.max_jobs = request.max_jobs
    search.updated_at = utc_now()
    session.commit()
    return _response(search)


def delete_discovery_search(session: Session, saved_search_id: str) -> None:
    search = session.get(DiscoverySavedSearch, saved_search_id)
    if search is None:
        raise JoltNotFoundError("Saved discovery search was not found.")
    session.delete(search)
    session.commit()
