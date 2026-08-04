from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.capture_archival import (
    ARCHIVED_CAPTURE_STATUS,
    CaptureBatchArchiveResult,
    archive_capture_run,
)
from jolt.database import CaptureItem, CaptureRun
from jolt.opportunity_index import list_opportunity_index


class PendingInboxClearResponse(BaseModel):
    pending_before: int
    pending_after: int
    cleared_pending_count: int
    archived_capture_run_count: int
    protected_pending_count: int
    archived_runs: list[CaptureBatchArchiveResult]


def clear_pending_review_inbox(session: Session) -> PendingInboxClearResponse:
    """Archive only capture batches composed entirely of current pending postings."""

    pending_before_items = list_opportunity_index(session)
    pending_ids = {item.posting_id for item in pending_before_items}
    if not pending_ids:
        return PendingInboxClearResponse(
            pending_before=0,
            pending_after=0,
            cleared_pending_count=0,
            archived_capture_run_count=0,
            protected_pending_count=0,
            archived_runs=[],
        )

    candidate_run_ids = set(
        session.scalars(
            select(CaptureItem.capture_run_id)
            .join(CaptureRun, CaptureRun.id == CaptureItem.capture_run_id)
            .where(CaptureItem.posting_id.in_(pending_ids))
            .where(CaptureRun.status != ARCHIVED_CAPTURE_STATUS)
        ).all()
    )

    eligible_run_ids: list[str] = []
    protected_pending_ids: set[str] = set()
    for run_id in sorted(candidate_run_ids):
        run = session.get(CaptureRun, run_id)
        if run is None:
            continue
        run_posting_ids = {
            posting_id
            for posting_id in session.scalars(
                select(CaptureItem.posting_id)
                .where(CaptureItem.capture_run_id == run_id)
                .where(CaptureItem.posting_id.is_not(None))
            ).all()
            if posting_id is not None
        }
        pending_in_run = run_posting_ids & pending_ids
        if run.status == "running" or not run_posting_ids.issubset(pending_ids):
            protected_pending_ids.update(pending_in_run)
            continue
        eligible_run_ids.append(run_id)

    archived_runs: list[CaptureBatchArchiveResult] = []
    try:
        for run_id in eligible_run_ids:
            archived_runs.append(archive_capture_run(session, run_id, commit=False))
        session.commit()
    except Exception:
        session.rollback()
        raise

    pending_after = len(list_opportunity_index(session))
    return PendingInboxClearResponse(
        pending_before=len(pending_before_items),
        pending_after=pending_after,
        cleared_pending_count=max(0, len(pending_before_items) - pending_after),
        archived_capture_run_count=len(archived_runs),
        protected_pending_count=len(protected_pending_ids),
        archived_runs=archived_runs,
    )
