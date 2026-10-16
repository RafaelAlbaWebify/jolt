"""Append-only source observation receipts, independent of transient capture retention."""

from __future__ import annotations

import hashlib
import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.capture_artifacts import CaptureArtifact
from jolt.database import (
    CaptureItem,
    CaptureRun,
    PortalSourceObservation,
    PostingSourceIdentity,
    utc_now,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def record_portal_observation(
    session: Session, *, capture_item_id: str, artifact_sha256: str
) -> PortalSourceObservation:
    """Persist a verified capture occurrence once, without storing raw descriptions."""
    item = session.get(CaptureItem, capture_item_id)
    if item is None or item.detail_status != "verified" or not item.posting_id:
        raise ValueError("A verified, promoted capture item is required")
    run = session.get(CaptureRun, item.capture_run_id)
    if run is None or run.source not in {"linkedin", "indeed", "infojobs", "jobgether"}:
        raise ValueError("Unsupported capture source")
    if not _SHA256.fullmatch(artifact_sha256):
        raise ValueError("A validated artifact SHA-256 is required")
    artifact = session.scalar(
        select(CaptureArtifact).where(
            CaptureArtifact.capture_item_id == item.id,
            CaptureArtifact.content_hash == artifact_sha256,
        )
    )
    if (
        artifact is None
        or hashlib.sha256(artifact.raw_payload.encode("utf-8")).hexdigest() != artifact_sha256
    ):
        raise ValueError("Capture evidence artifact hash mismatch")
    source = session.scalar(
        select(PostingSourceIdentity).where(
            PostingSourceIdentity.portal == run.source,
            PostingSourceIdentity.source_job_id == item.source_job_id,
            PostingSourceIdentity.posting_id == item.posting_id,
        )
    )
    if source is None:
        raise ValueError("Verified source identity must exist before recording observation")

    existing = session.scalar(
        select(PortalSourceObservation).where(
            PortalSourceObservation.portal == run.source,
            PortalSourceObservation.capture_item_id == item.id,
        )
    )
    if existing is not None:
        if (
            existing.artifact_sha256 != artifact_sha256
            or existing.posting_id_at_capture != item.posting_id
        ):
            raise ValueError("Capture occurrence cannot be rewritten")
        return existing

    row = PortalSourceObservation(
        id=str(uuid4()),
        portal=run.source,
        source_job_id=item.source_job_id,
        source_url=item.source_url,
        posting_id_at_capture=item.posting_id,
        capture_run_id=run.id,
        capture_item_id=item.id,
        source_document_id_at_capture=item.source_document_id,
        artifact_sha256=artifact_sha256,
        observed_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def list_portal_observations(session: Session, posting_id: str) -> list[PortalSourceObservation]:
    return list(
        session.scalars(
            select(PortalSourceObservation)
            .where(PortalSourceObservation.posting_id_at_capture == posting_id)
            .order_by(PortalSourceObservation.observed_at, PortalSourceObservation.id)
        ).all()
    )
