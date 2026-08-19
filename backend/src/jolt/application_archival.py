from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Application, ApplicationEvent, utc_now
from jolt.errors import JoltNotFoundError

ARCHIVED_APPLICATION_STATUS = "archived"
DEFAULT_RESTORE_STATUS = "preparing"


class ArchivedApplicationReadOnlyError(ValueError):
    """Raised when an operational write targets an archived application."""


class ApplicationArchiveRequest(BaseModel):
    notes: str = Field(default="", max_length=4000)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str) -> str:
        return value.strip()


class ApplicationArchiveResponse(BaseModel):
    application_id: str
    posting_id: str
    previous_status: str
    status: str
    archived: bool


def require_writable_application(session: Session, application_id: str) -> Application:
    """Return an application only when operational records may still be changed."""

    application = session.get(Application, application_id)
    if application is None:
        raise JoltNotFoundError("Application was not found.")
    if application.status == ARCHIVED_APPLICATION_STATUS:
        raise ArchivedApplicationReadOnlyError(
            "Archived applications are read-only. Restore the application before making changes."
        )
    return application


def _latest_archive_event(session: Session, application_id: str) -> ApplicationEvent | None:
    return session.scalar(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application_id)
        .where(ApplicationEvent.event_type == "application_archived")
        .order_by(ApplicationEvent.occurred_at.desc())
    )


def archive_application_card(
    session: Session,
    application_id: str,
    request: ApplicationArchiveRequest | None = None,
) -> ApplicationArchiveResponse:
    application = session.get(Application, application_id)
    if application is None:
        raise JoltNotFoundError("Application was not found.")
    if application.status == ARCHIVED_APPLICATION_STATUS:
        return ApplicationArchiveResponse(
            application_id=application.id,
            posting_id=application.posting_id,
            previous_status=ARCHIVED_APPLICATION_STATUS,
            status=application.status,
            archived=True,
        )

    previous = application.status
    now = utc_now()
    notes = (request.notes if request else "") or "Archived from the Applications board."
    application.status = ARCHIVED_APPLICATION_STATUS
    application.updated_at = now
    session.add(
        ApplicationEvent(
            id=str(uuid4()),
            application_id=application.id,
            event_type="application_archived",
            from_status=previous,
            to_status=ARCHIVED_APPLICATION_STATUS,
            notes=notes,
            occurred_at=now,
        )
    )
    session.commit()
    return ApplicationArchiveResponse(
        application_id=application.id,
        posting_id=application.posting_id,
        previous_status=previous,
        status=application.status,
        archived=True,
    )


def restore_application_card(
    session: Session,
    application_id: str,
    request: ApplicationArchiveRequest | None = None,
) -> ApplicationArchiveResponse:
    application = session.get(Application, application_id)
    if application is None:
        raise JoltNotFoundError("Application was not found.")
    if application.status != ARCHIVED_APPLICATION_STATUS:
        return ApplicationArchiveResponse(
            application_id=application.id,
            posting_id=application.posting_id,
            previous_status=application.status,
            status=application.status,
            archived=False,
        )

    archive_event = _latest_archive_event(session, application.id)
    restored_status = (
        archive_event.from_status
        if archive_event
        and archive_event.from_status
        and archive_event.from_status != ARCHIVED_APPLICATION_STATUS
        else DEFAULT_RESTORE_STATUS
    )
    previous = application.status
    now = utc_now()
    notes = (
        request.notes if request else ""
    ) or f"Restored to {restored_status} from the Applications board."
    application.status = restored_status
    application.updated_at = now
    session.add(
        ApplicationEvent(
            id=str(uuid4()),
            application_id=application.id,
            event_type="application_restored",
            from_status=previous,
            to_status=restored_status,
            notes=notes,
            occurred_at=now,
        )
    )
    session.commit()
    return ApplicationArchiveResponse(
        application_id=application.id,
        posting_id=application.posting_id,
        previous_status=previous,
        status=application.status,
        archived=False,
    )
