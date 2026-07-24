from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.application_records import ApplicationInterview, ApplicationTask
from jolt.automated_review import ensure_automated_reviews
from jolt.database import (
    Application,
    ApplicationEvent,
    Evaluation,
    Outcome,
    Posting,
    ReviewDecision,
    SourceDocument,
)


class OpportunityIndexItem(BaseModel):
    posting_id: str
    evaluation_id: str
    source_url: str
    title: str
    company: str
    location: str
    recommendation: str
    confidence: str
    ranking_score: int
    review_decision: str | None = None
    application_id: str | None = None
    application_status: str | None = None
    outcome_type: str | None = None
    last_activity_at: str | None = None
    next_due_at: str | None = None
    next_due_kind: str | None = None
    document_state: str | None = None
    overdue: bool = False


def list_opportunity_index(
    session: Session, *, include_applied: bool = False
) -> list[OpportunityIndexItem]:
    """Return compact queue metadata without constructing full review detail."""
    ensure_automated_reviews(session)

    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()
    source_documents = {item.id: item for item in session.scalars(select(SourceDocument)).all()}

    latest_evaluations: dict[str, Evaluation] = {}
    for evaluation in session.scalars(
        select(Evaluation).order_by(Evaluation.created_at.desc())
    ).all():
        latest_evaluations.setdefault(evaluation.posting_id, evaluation)

    latest_reviews: dict[str, ReviewDecision] = {}
    for review in session.scalars(
        select(ReviewDecision).order_by(ReviewDecision.reviewed_at.desc())
    ).all():
        latest_reviews.setdefault(review.posting_id, review)

    applications = {
        application.posting_id: application
        for application in session.scalars(select(Application)).all()
    }
    outcomes = {
        outcome.application_id: outcome
        for outcome in session.scalars(select(Outcome)).all()
        if outcome.application_id
    }

    latest_activity: dict[str, datetime] = {}
    for event in session.scalars(
        select(ApplicationEvent).order_by(ApplicationEvent.occurred_at.desc())
    ).all():
        latest_activity.setdefault(event.application_id, event.occurred_at)

    next_tasks: dict[str, ApplicationTask] = {}
    for task in session.scalars(
        select(ApplicationTask)
        .where(ApplicationTask.status == "open", ApplicationTask.due_at.is_not(None))
        .order_by(ApplicationTask.due_at)
    ).all():
        next_tasks.setdefault(task.application_id, task)

    next_interviews: dict[str, ApplicationInterview] = {}
    for interview in session.scalars(
        select(ApplicationInterview)
        .where(ApplicationInterview.status == "scheduled")
        .order_by(ApplicationInterview.scheduled_at)
    ).all():
        next_interviews.setdefault(interview.application_id, interview)

    now = datetime.now(UTC)
    results: list[OpportunityIndexItem] = []
    for posting in postings:
        evaluation = latest_evaluations.get(posting.id)
        if evaluation is None:
            continue
        application = applications.get(posting.id)
        if application is not None and not include_applied:
            continue
        review = latest_reviews.get(posting.id)
        outcome = outcomes.get(application.id) if application else None
        source_document = source_documents.get(posting.source_document_id)

        task = next_tasks.get(application.id) if application else None
        interview = next_interviews.get(application.id) if application else None
        due_at: datetime | None = None
        due_kind: str | None = None
        if task and interview:
            if task.due_at and task.due_at <= interview.scheduled_at:
                due_at, due_kind = task.due_at, "task"
            else:
                due_at, due_kind = interview.scheduled_at, "interview"
        elif task:
            due_at, due_kind = task.due_at, "task"
        elif interview:
            due_at, due_kind = interview.scheduled_at, "interview"

        results.append(
            OpportunityIndexItem(
                posting_id=posting.id,
                evaluation_id=evaluation.id,
                source_url=(source_document.source_url if source_document else posting.canonical_url),
                title=posting.title,
                company=posting.company,
                location=posting.location,
                recommendation=evaluation.recommendation,
                confidence=evaluation.confidence,
                ranking_score=evaluation.ranking_score,
                review_decision=review.decision if review else None,
                application_id=application.id if application else None,
                application_status=application.status if application else None,
                outcome_type=outcome.outcome_type if outcome else None,
                last_activity_at=(latest_activity.get(application.id).isoformat() if application and latest_activity.get(application.id) else application.updated_at.isoformat() if application else None),
                next_due_at=due_at.isoformat() if due_at else None,
                next_due_kind=due_kind,
                document_state=("resume attached" if application and application.resume_used.strip() else "resume missing") if application else "not started",
                overdue=bool(due_at and due_at < now),
            )
        )

    return results
