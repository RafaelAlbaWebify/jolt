from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jolt.database import (
    CaptureItem,
    CaptureRun,
    MarketIntelligenceObservation,
    Posting,
    SourceDocument,
    utc_now,
)
from jolt.errors import JoltNotFoundError


def extract_market_intelligence_observations(
    session: Session,
    capture_run_id: str,
) -> int:
    """Persist deterministic market evidence without candidate-fit judgments."""

    run = session.get(CaptureRun, capture_run_id)
    if run is None:
        raise JoltNotFoundError("Capture run was not found.")

    captured_at = run.completed_at or run.started_at
    items = list(
        session.scalars(
            select(CaptureItem)
            .where(CaptureItem.capture_run_id == capture_run_id)
            .where(CaptureItem.detail_status == "verified")
            .where(CaptureItem.posting_id.is_not(None))
            .where(CaptureItem.source_document_id.is_not(None))
        ).all()
    )

    created = 0
    for item in items:
        if not item.posting_id or not item.source_document_id:
            continue
        existing = session.scalar(
            select(MarketIntelligenceObservation.id)
            .where(MarketIntelligenceObservation.source_capture_run_id == capture_run_id)
            .where(MarketIntelligenceObservation.source_job_id == item.source_job_id)
            .limit(1)
        )
        if existing is not None:
            continue

        posting = session.get(Posting, item.posting_id)
        source = session.get(SourceDocument, item.source_document_id)
        if posting is None or source is None:
            continue

        observation = MarketIntelligenceObservation(
            id=str(uuid4()),
            source_capture_run_id=capture_run_id,
            source_job_id=item.source_job_id,
            posting_identity_key=posting.identity_key,
            source_url=source.source_url or posting.canonical_url or item.source_url,
            title=item.title or posting.title,
            company=item.company or posting.company,
            location=item.location or posting.location,
            description=source.raw_text,
            # Legacy schema columns intentionally stay neutral. Market observations are evidence,
            # not local recommendation/fit authority.
            engine_version="",
            recommendation="",
            confidence="",
            ranking_score=None,
            reasons_json="[]",
            captured_at=source.captured_at or captured_at,
            observed_at=utc_now(),
        )
        session.add(observation)
        created += 1

    session.flush()
    return created


def backfill_market_intelligence_observations(
    session: Session,
) -> dict[str, int]:
    """Backfill deterministic observations for every completed historical capture."""

    runs = list(
        session.scalars(
            select(CaptureRun)
            .where(CaptureRun.status != "running")
            .order_by(CaptureRun.started_at.asc(), CaptureRun.id.asc())
        ).all()
    )
    created = 0
    for run in runs:
        created += extract_market_intelligence_observations(session, run.id)

    existing = int(session.scalar(select(func.count(MarketIntelligenceObservation.id))) or 0)
    return {
        "capture_run_count": len(runs),
        "created_observation_count": created,
        "total_observation_count": existing,
    }
