from __future__ import annotations

from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from jolt.application_archival import ARCHIVED_APPLICATION_STATUS
from jolt.database import Application, ApplicationEvent, Posting, SourceDocument, utc_now
from jolt.errors import JoltNotFoundError
from jolt.url_identity import canonicalize_source_url
from jolt.workflow import posting_identity_key


class ApplicationMetadataUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    job_url: str | None = None
    application_url: str | None = None
    notes: str | None = None


class ApplicationMetadataResponse(BaseModel):
    application_id: str
    posting_id: str
    status: str
    title: str
    company: str
    location: str
    job_url: str
    application_url: str
    notes: str
    changed_fields: list[str]


def _validated_url(value: str, label: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    parts = urlsplit(stripped)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"{label} must be a valid http/https URL.")
    return stripped


def _identity_for_url(
    session: Session,
    posting: Posting,
    canonical_url: str,
) -> str:
    source = session.get(SourceDocument, posting.source_document_id)
    content_hash = source.content_hash if source is not None else ""
    if not canonical_url and not content_hash:
        raise ValueError("This posting has no source hash available for URL-less identity.")
    return posting_identity_key(canonical_url, content_hash)


def _change_summary(changes: list[tuple[str, str, str]]) -> str:
    return "; ".join(
        f"{label}: {before or '—'} → {after or '—'}" for label, before, after in changes
    )


def update_application_metadata(
    session: Session,
    application_id: str,
    request: ApplicationMetadataUpdate,
) -> ApplicationMetadataResponse:
    application = session.get(Application, application_id)
    if application is None:
        raise JoltNotFoundError("Application was not found.")
    if application.status == ARCHIVED_APPLICATION_STATUS:
        raise ValueError(
            "Archived applications are read-only. Restore the application before editing."
        )

    posting = session.get(Posting, application.posting_id)
    if posting is None:
        raise JoltNotFoundError("Application posting was not found.")

    fields = request.model_fields_set
    pending_posting: dict[str, str] = {}
    pending_application: dict[str, str] = {}
    changes: list[tuple[str, str, str]] = []

    for field, label in (
        ("title", "Job title"),
        ("company", "Company"),
        ("location", "Location"),
    ):
        if field not in fields:
            continue
        raw = getattr(request, field)
        if raw is None:
            raise ValueError(f"{label} cannot be null.")
        value = raw.strip()
        before = str(getattr(posting, field))
        if value != before:
            pending_posting[field] = value
            changes.append((label, before, value))

    if "job_url" in fields:
        if request.job_url is None:
            raise ValueError("Job posting URL cannot be null.")
        validated = _validated_url(request.job_url, "Job posting URL")
        canonical = canonicalize_source_url(validated) if validated else ""
        new_identity = _identity_for_url(session, posting, canonical)
        collision = session.scalar(
            select(Posting).where(
                Posting.identity_key == new_identity,
                Posting.id != posting.id,
            )
        )
        if collision is not None:
            raise ValueError(
                "This job URL already belongs to another JOLT opportunity "
                f"(posting_id={collision.id})."
            )
        if canonical != posting.canonical_url:
            pending_posting["canonical_url"] = canonical
            pending_posting["identity_key"] = new_identity
            changes.append(("Job URL", posting.canonical_url, canonical))

    if "application_url" in fields:
        if request.application_url is None:
            raise ValueError("Application/Apply URL cannot be null.")
        value = _validated_url(request.application_url, "Application/Apply URL")
        if value != application.application_url:
            pending_application["application_url"] = value
            changes.append(("Application/Apply URL", application.application_url, value))

    if "notes" in fields:
        if request.notes is None:
            raise ValueError("Notes cannot be null.")
        value = request.notes.strip()
        if value != application.notes:
            pending_application["notes"] = value
            changes.append(("Notes", application.notes, value))

    if not changes:
        return ApplicationMetadataResponse(
            application_id=application.id,
            posting_id=posting.id,
            status=application.status,
            title=posting.title,
            company=posting.company,
            location=posting.location,
            job_url=posting.canonical_url,
            application_url=application.application_url,
            notes=application.notes,
            changed_fields=[],
        )

    now = utc_now()
    try:
        for field, value in pending_posting.items():
            setattr(posting, field, value)
        for field, value in pending_application.items():
            setattr(application, field, value)
        application.updated_at = now

        session.add(
            ApplicationEvent(
                id=str(uuid4()),
                application_id=application.id,
                event_type="metadata_updated",
                from_status=application.status,
                to_status=application.status,
                notes=_change_summary(changes),
                occurred_at=now,
            )
        )
        session.flush()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError("This job URL already belongs to another JOLT opportunity.") from exc
    except Exception:
        session.rollback()
        raise

    return ApplicationMetadataResponse(
        application_id=application.id,
        posting_id=posting.id,
        status=application.status,
        title=posting.title,
        company=posting.company,
        location=posting.location,
        job_url=posting.canonical_url,
        application_url=application.application_url,
        notes=application.notes,
        changed_fields=[label for label, _, _ in changes],
    )
