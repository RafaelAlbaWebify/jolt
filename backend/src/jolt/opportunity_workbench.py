from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Application, Evaluation, Outcome, Posting, ReviewDecision
from jolt.schemas import OpportunitySummary


def list_opportunity_workbench(session: Session) -> list[OpportunitySummary]:
    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()
    results: list[OpportunitySummary] = []

    for posting in postings:
        evaluation = session.scalar(
            select(Evaluation)
            .where(Evaluation.posting_id == posting.id)
            .order_by(Evaluation.created_at.desc())
        )
        if evaluation is None:
            continue

        review = session.scalar(
            select(ReviewDecision)
            .where(ReviewDecision.posting_id == posting.id)
            .order_by(ReviewDecision.reviewed_at.desc())
        )
        application = session.scalar(
            select(Application).where(Application.posting_id == posting.id)
        )
        outcome = (
            session.scalar(select(Outcome).where(Outcome.application_id == application.id))
            if application
            else None
        )

        results.append(
            OpportunitySummary(
                posting_id=posting.id,
                evaluation_id=evaluation.id,
                source_url=posting.source_document.source_url,
                title=posting.title,
                company=posting.company,
                location=posting.location,
                recommendation=evaluation.recommendation,
                confidence=evaluation.confidence,
                ranking_score=evaluation.ranking_score,
                reasons=json.loads(evaluation.reasons_json),
                profile_version_id=evaluation.profile_version_id,
                engine_version=evaluation.engine_version,
                review_decision=review.decision if review else None,
                application_id=application.id if application else None,
                application_status=application.status if application else None,
                outcome_type=outcome.outcome_type if outcome else None,
            )
        )

    return results
