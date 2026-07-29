from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from jolt.database import Application, ApplicationEvent, utc_now
from uuid import uuid4

ARCHIVED_APPLICATION_STATUS = "archived"


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


def archive_application_card(
    session: Session,
    application_id: str,
    request: ApplicationArchiveRequest | None = None,
) -> ApplicationArchiveResponse:
    application = session.get(Application, application_id)
    if application is None:
        raise LookupError("Application was not found.")
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
