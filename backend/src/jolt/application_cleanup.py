from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import delete, func, select
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


def _owned_record_count(session: Session, model: type, application_id: str) -> int:
    count = session.scalar(
        select(func.count()).select_from(model).where(model.application_id == application_id)
    )
    return int(count or 0)


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
        event_count = _owned_record_count(session, ApplicationEvent, application_id)
        outcome_count = _owned_record_count(session, Outcome, application_id)
        task_count = _owned_record_count(session, ApplicationTask, application_id)
        interview_count = _owned_record_count(session, ApplicationInterview, application_id)
        contact_count = _owned_record_count(session, ApplicationContact, application_id)
        document_count = _owned_record_count(session, ApplicationDocument, application_id)

        session.execute(
            delete(ApplicationEvent).where(ApplicationEvent.application_id == application_id)
        )
        session.execute(delete(Outcome).where(Outcome.application_id == application_id))
        session.execute(
            delete(ApplicationTask).where(ApplicationTask.application_id == application_id)
        )
        session.execute(
            delete(ApplicationInterview).where(
                ApplicationInterview.application_id == application_id
            )
        )
        session.execute(
            delete(ApplicationContact).where(ApplicationContact.application_id == application_id)
        )
        session.execute(
            delete(ApplicationDocument).where(
                ApplicationDocument.application_id == application_id
            )
        )
        session.delete(application)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return ApplicationDeleteResponse(
        application_id=application_id,
        posting_id=posting_id,
        deleted=True,
        deleted_event_count=event_count,
        deleted_outcome_count=outcome_count,
        deleted_task_count=task_count,
        deleted_interview_count=interview_count,
        deleted_contact_count=contact_count,
        deleted_document_count=document_count,
    )
