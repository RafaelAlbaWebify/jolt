from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Application, ApplicationEvent, Outcome
from jolt.schemas import ApplicationEventResponse, ApplicationResponse


def build_application_response(session: Session, application: Application) -> ApplicationResponse:
    """Build the canonical application response without importing workflow orchestration."""
    events = session.scalars(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application.id)
        .order_by(ApplicationEvent.occurred_at)
    ).all()
    outcome = session.scalar(select(Outcome).where(Outcome.application_id == application.id))
    return ApplicationResponse(
        application_id=application.id,
        posting_id=application.posting_id,
        status=application.status,
        application_url=application.application_url,
        resume_used=application.resume_used,
        notes=application.notes,
        outcome_type=outcome.outcome_type if outcome else None,
        events=[
            ApplicationEventResponse(
                event_id=event.id,
                event_type=event.event_type,
                from_status=event.from_status,
                to_status=event.to_status,
                notes=event.notes,
                occurred_at=event.occurred_at.isoformat(),
            )
            for event in events
        ],
    )
