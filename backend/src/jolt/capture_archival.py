from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Application, CaptureItem, CaptureRun, Posting, ReviewDecision
from jolt.errors import JoltNotFoundError

ARCHIVED_CAPTURE_STATUS = "archived"
LEGACY_UNKNOWN_STOP_REASON = "legacy_unknown"
ARCHIVABLE_CAPTURE_SOURCES = {"linkedin"}
ARCHIVABLE_CAPTURE_MODES = {"fixture", "supervised_live"}


class CaptureBatchArchiveResult(BaseModel):
    capture_run_id: str
    previous_status: str
    status: str
    archived_item_count: int
    hidden_pending_posting_count: int
    protected_posting_count: int


class CaptureBatchArchiveSummary(BaseModel):
    archived_capture_run_count: int
    archived_item_count: int
    hidden_pending_posting_count: int
    protected_posting_count: int
    archived_runs: list[CaptureBatchArchiveResult]


def _posting_has_user_state(session: Session, posting_id: str) -> bool:
    review = session.scalar(select(ReviewDecision).where(ReviewDecision.posting_id == posting_id))
    if review is not None:
        return True
    application = session.scalar(select(Application).where(Application.posting_id == posting_id))
    return application is not None


def _run_items(session: Session, capture_run_id: str) -> list[CaptureItem]:
    return list(
        session.scalars(
            select(CaptureItem).where(CaptureItem.capture_run_id == capture_run_id)
        ).all()
    )


def _has_legacy_unknown_count(run: CaptureRun, items: list[CaptureItem]) -> bool:
    return (
        run.requested_item_limit is None
        and run.observed_item_count == 0
        and bool(items)
        and run.stop_reason in {"", LEGACY_UNKNOWN_STOP_REASON}
    )


def archive_capture_run(
    session: Session,
    capture_run_id: str,
    *,
    commit: bool = True,
) -> CaptureBatchArchiveResult:
    """Archive a capture run without physically deleting shared opportunity records.

    Archived capture runs remain in the database for traceability, but the default
    Opportunities review inbox excludes postings whose only capture backing is archived.
    This avoids foreign-key failures around central Posting records while giving the user
    a safe way to clear stale imported batches from the review queue.

    Legacy rows created before observed-count metadata existed retain explicit unknown
    provenance. Archival must not reinterpret their default zero as an observed count.
    """
    run = session.get(CaptureRun, capture_run_id)
    if run is None:
        raise JoltNotFoundError("Capture run was not found.")
    if run.status == "running":
        raise ValueError("A running capture run must be stopped before it can be archived.")

    previous_status = run.status
    items = _run_items(session, capture_run_id)
    protected_posting_ids: set[str] = set()
    hidden_pending_posting_ids: set[str] = set()

    for item in items:
        if not item.posting_id:
            continue
        posting = session.get(Posting, item.posting_id)
        if posting is None:
            continue
        if _posting_has_user_state(session, posting.id):
            protected_posting_ids.add(posting.id)
        else:
            hidden_pending_posting_ids.add(posting.id)

    legacy_unknown_count = _has_legacy_unknown_count(run, items)
    run.status = ARCHIVED_CAPTURE_STATUS
    if not legacy_unknown_count:
        run.stop_reason = "archived_by_user"
    if commit:
        session.commit()
    else:
        session.flush()

    return CaptureBatchArchiveResult(
        capture_run_id=run.id,
        previous_status=previous_status,
        status=run.status,
        archived_item_count=len(items),
        hidden_pending_posting_count=len(hidden_pending_posting_ids),
        protected_posting_count=len(protected_posting_ids),
    )


def list_archivable_capture_runs(session: Session) -> list[CaptureRun]:
    return list(
        session.scalars(
            select(CaptureRun)
            .where(CaptureRun.status != ARCHIVED_CAPTURE_STATUS)
            .order_by(CaptureRun.started_at.desc())
        ).all()
    )


def archive_imported_capture_runs(session: Session) -> CaptureBatchArchiveSummary:
    results: list[CaptureBatchArchiveResult] = []
    for run in list_archivable_capture_runs(session):
        if run.source not in ARCHIVABLE_CAPTURE_SOURCES:
            continue
        if run.mode not in ARCHIVABLE_CAPTURE_MODES:
            continue
        results.append(archive_capture_run(session, run.id))

    return CaptureBatchArchiveSummary(
        archived_capture_run_count=len(results),
        archived_item_count=sum(item.archived_item_count for item in results),
        hidden_pending_posting_count=sum(item.hidden_pending_posting_count for item in results),
        protected_posting_count=sum(item.protected_posting_count for item in results),
        archived_runs=results,
    )
