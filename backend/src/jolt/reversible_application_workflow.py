from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Application, ApplicationEvent, Outcome, utc_now
from jolt.schemas import ApplicationResponse, ApplicationTransitionRequest
from jolt.workflow import _application_response

VALID_APPLICATION_STATUSES = {
    "preparing",
    "submitted",
    "acknowledged",
    "recruiter_screen",
    "technical_interview",
    "hiring_manager_interview",
    "final_interview",
    "offer",
    "rejected",
    "withdrawn",
    "no_response",
    "closed",
}

TERMINAL_APPLICATION_STATUSES = {"rejected", "withdrawn", "no_response", "closed"}


def _outcome_history_note(outcome: Outcome) -> str:
    details = [f"Previous outcome: {outcome.outcome_type}."]
    if outcome.reason_code:
        details.append(f"Reason: {outcome.reason_code}.")
    if outcome.notes:
        details.append(f"Outcome notes: {outcome.notes}")
    return " ".join(details)


def transition_application_reversibly(
    session: Session,
    application_id: str,
    request: ApplicationTransitionRequest,
) -> ApplicationResponse:
    """Move an application to any valid stage while preserving an audit trail."""

    application = session.get(Application, application_id)
    if application is None:
        raise LookupError("Application was not found.")
    if request.status not in VALID_APPLICATION_STATUSES:
        raise ValueError(f"Unknown application status: {request.status}.")
    if request.status == application.status:
        return _application_response(session, application)

    previous = application.status
    now = utc_now()
    event_type = "status_changed"
    notes = request.notes.strip()

    existing_outcome = session.scalar(
        select(Outcome).where(Outcome.application_id == application_id)
    )
    reopening = (
        previous in TERMINAL_APPLICATION_STATUSES
        and request.status not in TERMINAL_APPLICATION_STATUSES
    )
    if reopening:
        event_type = "application_reopened"
        if existing_outcome is not None:
            preserved = _outcome_history_note(existing_outcome)
            notes = f"{notes} {preserved}".strip()
            session.delete(existing_outcome)

    application.status = request.status
    application.updated_at = now
    session.add(
        ApplicationEvent(
            id=str(uuid4()),
            application_id=application.id,
            event_type=event_type,
            from_status=previous,
            to_status=request.status,
            notes=notes,
            occurred_at=now,
        )
    )
    session.commit()
    return _application_response(session, application)
