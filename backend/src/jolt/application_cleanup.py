from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.orm import Session

from jolt.application_archival import ARCHIVED_APPLICATION_STATUS
from jolt.application_records import (
    ApplicationContact,
    ApplicationDocument,
    ApplicationInterview,
    ApplicationTask,
)
from jolt.database import Application, ApplicationEvent, Outcome


class ApplicationDeleteResponse(BaseModel):
    application_id: str
    posting_id: str
    deleted: bool
    deleted_event_count: int
    deleted_outcome_count: int
    deleted_task_count: int
    deleted_interview_count: int
    deleted_contact_count: int
    deleted_document_count: int


def delete_archived_application(
    session: Session,
    application_id: str,
) -> ApplicationDeleteResponse:
    """Permanently delete an archived application and application-owned records only."""

    application = session.get(Application, application_id)
    if application is None:
        raise LookupError("Application was not found.")
    if application.status != ARCHIVED_APPLICATION_STATUS:
        raise ValueError("Only an archived application can be permanently deleted.")

    posting_id = application.posting_id
    try:
        event_count = session.execute(
            delete(ApplicationEvent).where(ApplicationEvent.application_id == application_id)
        ).rowcount or 0
        outcome_count = session.execute(
            delete(Outcome).where(Outcome.application_id == application_id)
        ).rowcount or 0
        task_count = session.execute(
            delete(ApplicationTask).where(ApplicationTask.application_id == application_id)
        ).rowcount or 0
        interview_count = session.execute(
            delete(ApplicationInterview).where(
                ApplicationInterview.application_id == application_id
            )
        ).rowcount or 0
        contact_count = session.execute(
            delete(ApplicationContact).where(ApplicationContact.application_id == application_id)
        ).rowcount or 0
        document_count = session.execute(
            delete(ApplicationDocument).where(
                ApplicationDocument.application_id == application_id
            )
        ).rowcount or 0
        session.delete(application)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return ApplicationDeleteResponse(
        application_id=application_id,
        posting_id=posting_id,
        deleted=True,
        deleted_event_count=int(event_count),
        deleted_outcome_count=int(outcome_count),
        deleted_task_count=int(task_count),
        deleted_interview_count=int(interview_count),
        deleted_contact_count=int(contact_count),
        deleted_document_count=int(document_count),
    )
