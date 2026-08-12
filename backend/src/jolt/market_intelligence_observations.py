from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jolt.database import (
    CaptureItem,
    CaptureRun,
    Evaluation,
    MarketIntelligenceObservation,
    Posting,
    utc_now,
)
from jolt.strategy_runtime import ENGINE_VERSION


def _effective_evaluation(
    session: Session,
    posting_id: str,
) -> Evaluation | None:
    current = session.scalar(
        select(Evaluation)
        .where(Evaluation.posting_id == posting_id)
        .where(Evaluation.engine_version == ENGINE_VERSION)
        .order_by(
            Evaluation.created_at.desc(),
            Evaluation.id.desc(),
        )
        .limit(1)
    )

    if current is not None:
        return current

    return session.scalar(
        select(Evaluation)
        .where(Evaluation.posting_id == posting_id)
        .order_by(
            Evaluation.created_at.desc(),
            Evaluation.id.desc(),
        )
        .limit(1)
    )


def extract_market_intelligence_observations(
    session: Session,
    capture_run_id: str,
) -> int:
    """Persist durable market observations independently of raw capture rows."""

    run = session.get(CaptureRun, capture_run_id)
    if run is None:
        raise LookupError("Capture run was not found.")

    captured_at = run.completed_at or run.started_at

    items = list(
        session.scalars(
            select(CaptureItem)
            .where(CaptureItem.capture_run_id == capture_run_id)
            .where(CaptureItem.detail_status == "verified")
            .where(CaptureItem.posting_id.is_not(None))
        ).all()
    )

    created = 0

    for item in items:
        if not item.posting_id:
            continue

        existing = session.scalar(
            select(MarketIntelligenceObservation.id)
            .where(
                MarketIntelligenceObservation.source_capture_run_id
                == capture_run_id
            )
            .where(
                MarketIntelligenceObservation.source_job_id
                == item.source_job_id
            )
            .limit(1)
        )
        if existing is not None:
            continue

        posting = session.get(Posting, item.posting_id)
        if posting is None:
            continue

        evaluation = _effective_evaluation(session, posting.id)

        observation = MarketIntelligenceObservation(
            id=str(uuid4()),
            source_capture_run_id=capture_run_id,
            source_job_id=item.source_job_id,
            posting_identity_key=posting.identity_key,
            source_url=posting.canonical_url or item.source_url,
            title=posting.title,
            company=posting.company,
            location=posting.location,
            description=posting.description,
            engine_version=evaluation.engine_version if evaluation else "",
            recommendation=evaluation.recommendation if evaluation else "",
            confidence=evaluation.confidence if evaluation else "",
            ranking_score=evaluation.ranking_score if evaluation else None,
            reasons_json=evaluation.reasons_json if evaluation else "[]",
            captured_at=captured_at,
            observed_at=utc_now(),
        )
        session.add(observation)
        created += 1

    session.flush()
    return created



def backfill_market_intelligence_observations(
    session: Session,
) -> dict[str, int]:
    """Backfill durable observations for every completed historical capture."""

    runs = list(
        session.scalars(
            select(CaptureRun)
            .where(CaptureRun.status != "running")
            .order_by(
                CaptureRun.started_at.asc(),
                CaptureRun.id.asc(),
            )
        ).all()
    )

    created = 0

    for run in runs:
        created += extract_market_intelligence_observations(
            session,
            run.id,
        )

    existing = int(
        session.scalar(
            select(func.count(MarketIntelligenceObservation.id))
        )
        or 0
    )

    return {
        "capture_run_count": len(runs),
        "created_observation_count": created,
        "total_observation_count": existing,
    }
