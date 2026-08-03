from __future__ import annotations

import json

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.capture_archival import ARCHIVED_CAPTURE_STATUS, LEGACY_UNKNOWN_STOP_REASON
from jolt.database import CaptureItem, CapturePage, CaptureRun


class CaptureMetadataRepairCandidate(BaseModel):
    capture_run_id: str
    persisted_item_count: int
    visible_item_count: int
    visible_unique_item_count: int
    current_stop_reason: str
    proposed_stop_reason: str


class CaptureMetadataRepairResult(BaseModel):
    apply: bool
    candidate_count: int
    repaired_count: int
    candidates: list[CaptureMetadataRepairCandidate]


def _run_items(session: Session, capture_run_id: str) -> list[CaptureItem]:
    return list(
        session.scalars(
            select(CaptureItem).where(CaptureItem.capture_run_id == capture_run_id)
        ).all()
    )


def _run_pages(session: Session, capture_run_id: str) -> list[CapturePage]:
    return list(
        session.scalars(
            select(CapturePage)
            .where(CapturePage.capture_run_id == capture_run_id)
            .order_by(CapturePage.page_number)
        ).all()
    )


def _visible_job_ids(pages: list[CapturePage]) -> list[str] | None:
    visible_ids: list[str] = []
    for page in pages:
        try:
            value = json.loads(page.visible_job_ids_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return None
        visible_ids.extend(value)
    return visible_ids


def _candidate_for_run(session: Session, run: CaptureRun) -> CaptureMetadataRepairCandidate | None:
    if run.status != ARCHIVED_CAPTURE_STATUS:
        return None
    if run.requested_item_limit is not None or run.observed_item_count != 0:
        return None
    if run.stop_reason != "archived_by_user":
        return None

    items = _run_items(session, run.id)
    pages = _run_pages(session, run.id)
    visible_ids = _visible_job_ids(pages)
    if not items or not pages or visible_ids is None:
        return None

    persisted_ids = [item.source_job_id for item in items]
    if len(set(persisted_ids)) != len(persisted_ids):
        return None
    if len(set(visible_ids)) != len(visible_ids):
        return None
    if set(persisted_ids) != set(visible_ids):
        return None

    return CaptureMetadataRepairCandidate(
        capture_run_id=run.id,
        persisted_item_count=len(persisted_ids),
        visible_item_count=len(visible_ids),
        visible_unique_item_count=len(set(visible_ids)),
        current_stop_reason=run.stop_reason,
        proposed_stop_reason=LEGACY_UNKNOWN_STOP_REASON,
    )


def repair_archived_legacy_capture_metadata(
    session: Session, *, apply: bool = False
) -> CaptureMetadataRepairResult:
    """Restore unknown-count provenance without inventing an observed count.

    A row is repairable only when it is archived, has the legacy null/zero metadata
    shape, still says ``archived_by_user``, and its persisted item identities match
    the page-visible identities exactly with no duplicates. Dry-run is the default.
    """
    runs = session.scalars(select(CaptureRun).order_by(CaptureRun.started_at)).all()
    candidates: list[CaptureMetadataRepairCandidate] = []
    repairable_runs: list[CaptureRun] = []

    for run in runs:
        candidate = _candidate_for_run(session, run)
        if candidate is None:
            continue
        candidates.append(candidate)
        repairable_runs.append(run)

    if apply:
        for run in repairable_runs:
            run.stop_reason = LEGACY_UNKNOWN_STOP_REASON
        session.commit()

    return CaptureMetadataRepairResult(
        apply=apply,
        candidate_count=len(candidates),
        repaired_count=len(repairable_runs) if apply else 0,
        candidates=candidates,
    )
