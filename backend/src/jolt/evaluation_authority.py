from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.application_readiness import ApplicationReadiness
from jolt.database import Evaluation
from jolt.strategy_runtime import ENGINE_VERSION as STRATEGY_ENGINE_VERSION


def authoritative_evaluations(session: Session) -> dict[str, Evaluation]:
    """Select one stable evaluation per posting without creating derived records."""
    evaluations = session.scalars(select(Evaluation).order_by(Evaluation.created_at.desc())).all()
    strategy: dict[str, Evaluation] = {}
    fallback: dict[str, Evaluation] = {}
    for evaluation in evaluations:
        fallback.setdefault(evaluation.posting_id, evaluation)
        if evaluation.engine_version == STRATEGY_ENGINE_VERSION:
            strategy.setdefault(evaluation.posting_id, evaluation)
    return {posting_id: strategy.get(posting_id, evaluation) for posting_id, evaluation in fallback.items()}


def authoritative_evaluation(session: Session, posting_id: str) -> Evaluation | None:
    return authoritative_evaluations(session).get(posting_id)


def latest_readiness_report(session: Session, posting_id: str) -> ApplicationReadiness | None:
    return session.scalar(
        select(ApplicationReadiness)
        .where(ApplicationReadiness.posting_id == posting_id)
        .order_by(ApplicationReadiness.created_at.desc())
    )
