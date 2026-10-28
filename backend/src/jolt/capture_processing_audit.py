"""Read-only cross-check between verified capture evidence and persisted market observations.

This is a diagnostic, not a universal processing ledger or deletion authorization.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import CaptureItem, CaptureRun, MarketIntelligenceObservation


@dataclass(frozen=True)
class CaptureCoverage:
    capture_run_id: str
    expected: int
    observed: int
    missing: int
    unexpected: int
    complete: bool


def audit_market_capture_coverage(session: Session) -> list[CaptureCoverage]:
    """Compare (run, source-job) identities; never modify capture or market rows."""
    runs = session.scalars(select(CaptureRun.id).order_by(CaptureRun.id)).all()
    expected_pairs = set(
        session.execute(
            select(CaptureItem.capture_run_id, CaptureItem.source_job_id)
            .where(CaptureItem.detail_status == "verified")
            .where(CaptureItem.posting_id.is_not(None))
            .where(CaptureItem.source_document_id.is_not(None))
        ).all()
    )
    observed_pairs = set(
        session.execute(
            select(
                MarketIntelligenceObservation.source_capture_run_id,
                MarketIntelligenceObservation.source_job_id,
            )
        ).all()
    )
    results: list[CaptureCoverage] = []
    for run_id in runs:
        expected = {job_id for capture_id, job_id in expected_pairs if capture_id == run_id}
        observed = {job_id for capture_id, job_id in observed_pairs if capture_id == run_id}
        missing = expected - observed
        unexpected = observed - expected
        results.append(
            CaptureCoverage(
                capture_run_id=run_id,
                expected=len(expected),
                observed=len(observed),
                missing=len(missing),
                unexpected=len(unexpected),
                complete=not missing and not unexpected,
            )
        )
    return results
