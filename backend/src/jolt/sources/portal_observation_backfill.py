"""Conservative historical portal receipt backfill; operator controls commit/rollback.

Only existing promoted, verified items with intact artifacts and matching durable
portal identities qualify. Never reconstruct absent source detail or identity.
"""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.capture_artifacts import CaptureArtifact
from jolt.database import CaptureItem, CaptureRun, PortalSourceObservation
from jolt.sources.portal_observations import record_portal_observation


class PortalBackfillReport(BaseModel):
    eligible: int
    already_recorded: int
    rejected: int
    created: int
    rejected_item_ids: list[str]


def backfill_portal_observation_receipts(
    session: Session, *, commit: bool = False
) -> PortalBackfillReport:
    """Dry-run by default. Caller must explicitly opt into a database commit."""
    created = 0
    eligible = 0
    existing = 0
    rejected: list[str] = []
    with session.begin_nested() as nested:
        rows = session.execute(
            select(CaptureItem, CaptureRun)
            .join(CaptureRun, CaptureRun.id == CaptureItem.capture_run_id)
            .where(
                CaptureRun.source.in_(("linkedin", "indeed", "infojobs", "jobgether")),
                CaptureItem.detail_status == "verified",
                CaptureItem.posting_id.is_not(None),
            )
            .order_by(CaptureRun.started_at, CaptureItem.id)
        ).all()
        for item, run in rows:
            seen = session.scalar(
                select(PortalSourceObservation.id).where(
                    PortalSourceObservation.portal == run.source,
                    PortalSourceObservation.capture_item_id == item.id,
                )
            )
            if seen is not None:
                existing += 1
                continue
            artifact = session.scalar(
                select(CaptureArtifact)
                .where(CaptureArtifact.capture_item_id == item.id)
                .order_by(CaptureArtifact.id)
            )
            if artifact is None:
                rejected.append(item.id)
                continue
            try:
                with session.begin_nested():
                    receipt = record_portal_observation(
                        session, capture_item_id=item.id, artifact_sha256=artifact.content_hash
                    )
                    # Historical observation time comes from the recorded run, not backfill time.
                    receipt.observed_at = run.started_at
                    session.flush()
            except ValueError:
                rejected.append(item.id)
                continue
            eligible += 1
            created += 1
        report = PortalBackfillReport(
            eligible=eligible,
            already_recorded=existing,
            rejected=len(rejected),
            created=created,
            rejected_item_ids=rejected[:100],
        )
        if not commit:
            nested.rollback()
    if commit:
        session.commit()
    return report
