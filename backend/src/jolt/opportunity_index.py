from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.automated_review import ensure_automated_reviews
from jolt.database import (
    Application,
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


def list_opportunity_index(session: Session) -> list[OpportunityIndexItem]:
    """Return queue/application metadata without constructing full review detail."""
    ensure_automated_reviews(session)

    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()
    source_documents = {
        item.id: item for item in session.scalars(select(SourceDocument)).all()
    }

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

    results: list[OpportunityIndexItem] = []
    for posting in postings:
        evaluation = latest_evaluations.get(posting.id)
        if evaluation is None:
            continue
        review = latest_reviews.get(posting.id)
        application = applications.get(posting.id)
        outcome = outcomes.get(application.id) if application else None
        source_document = source_documents.get(posting.source_document_id)

        results.append(
            OpportunityIndexItem(
                posting_id=posting.id,
                evaluation_id=evaluation.id,
                source_url=(
                    source_document.source_url
                    if source_document
                    else posting.canonical_url
                ),
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
            )
        )

    return results
