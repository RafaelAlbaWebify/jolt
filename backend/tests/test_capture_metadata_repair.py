from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from jolt.capture_archival import archive_capture_run
from jolt.capture_metadata_repair import repair_archived_legacy_capture_metadata
from jolt.database import CaptureItem, CapturePage, CaptureRun, create_session_factory


def _session(tmp_path) -> Session:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")
    return factory()


def _add_legacy_run(
    session: Session,
    *,
    run_id: str,
    status: str,
    stop_reason: str,
    visible_ids: list[str],
    item_ids: list[str],
) -> CaptureRun:
    now = datetime.now(UTC)
    run = CaptureRun(
        id=run_id,
        source="linkedin",
        mode="supervised_live",
        status=status,
        search_url="https://example.test/jobs",
        warnings_json="[]",
        requested_item_limit=None,
        observed_item_count=0,
        stop_reason=stop_reason,
        started_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()
    session.add(
        CapturePage(
            id=f"page-{run_id}",
            capture_run_id=run_id,
            page_number=1,
            visible_job_ids_json=json.dumps(visible_ids),
            next_control_present=False,
            next_control_enabled=False,
        )
    )
    for source_job_id in item_ids:
        session.add(
            CaptureItem(
                id=f"item-{run_id}-{source_job_id}",
                capture_run_id=run_id,
                source_job_id=source_job_id,
                source_url=f"https://example.test/jobs/{source_job_id}",
                title=f"Role {source_job_id}",
                company="Example",
                location="Remote",
                detail_status="verified",
                verification_reasons_json="[]",
                source_document_id=None,
                posting_id=None,
            )
        )
    session.commit()
    return run


def test_archiving_legacy_run_preserves_unknown_count_provenance(tmp_path) -> None:
    session = _session(tmp_path)
    try:
        run = _add_legacy_run(
            session,
            run_id="legacy-run",
            status="completed",
            stop_reason="legacy_unknown",
            visible_ids=["job-1", "job-2"],
            item_ids=["job-1", "job-2"],
        )

        result = archive_capture_run(session, run.id)

        session.refresh(run)
        assert result.status == "archived"
        assert run.status == "archived"
        assert run.stop_reason == "legacy_unknown"
        assert run.observed_item_count == 0
        assert run.requested_item_limit is None
    finally:
        session.close()


def test_repair_is_dry_run_by_default_and_changes_only_provenance(tmp_path) -> None:
    session = _session(tmp_path)
    try:
        run = _add_legacy_run(
            session,
            run_id="affected-run",
            status="archived",
            stop_reason="archived_by_user",
            visible_ids=["job-1", "job-2", "job-3"],
            item_ids=["job-1", "job-2", "job-3"],
        )

        preview = repair_archived_legacy_capture_metadata(session)
        session.refresh(run)

        assert preview.apply is False
        assert preview.candidate_count == 1
        assert preview.repaired_count == 0
        assert run.stop_reason == "archived_by_user"
        assert run.observed_item_count == 0

        applied = repair_archived_legacy_capture_metadata(session, apply=True)
        session.refresh(run)

        assert applied.apply is True
        assert applied.candidate_count == 1
        assert applied.repaired_count == 1
        assert run.stop_reason == "legacy_unknown"
        assert run.observed_item_count == 0
        assert run.requested_item_limit is None
        assert session.query(CaptureItem).filter_by(capture_run_id=run.id).count() == 3
    finally:
        session.close()


def test_repair_refuses_rows_when_page_and_item_evidence_disagree(tmp_path) -> None:
    session = _session(tmp_path)
    try:
        run = _add_legacy_run(
            session,
            run_id="ambiguous-run",
            status="archived",
            stop_reason="archived_by_user",
            visible_ids=["job-1", "job-2"],
            item_ids=["job-1", "job-3"],
        )

        result = repair_archived_legacy_capture_metadata(session, apply=True)
        session.refresh(run)

        assert result.candidate_count == 0
        assert result.repaired_count == 0
        assert run.stop_reason == "archived_by_user"
        assert run.observed_item_count == 0
    finally:
        session.close()
