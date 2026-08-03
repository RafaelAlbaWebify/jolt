from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.application_cleanup import delete_archived_application
from jolt.application_records import (
    ApplicationContact,
    ApplicationDocument,
    ApplicationInterview,
    ApplicationTask,
)
from jolt.database import (
    Application,
    ApplicationEvent,
    CaptureItem,
    CapturePage,
    CaptureRun,
    Outcome,
    Posting,
    SourceDocument,
    create_session_factory,
)
from jolt.pending_inbox_cleanup import clear_pending_review_inbox


def _session(tmp_path) -> Session:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")
    return factory()


def _add_posting(session: Session, posting_id: str) -> Posting:
    now = datetime.now(UTC)
    source = SourceDocument(
        id=f"source-{posting_id}",
        source_type="test",
        source_url=f"https://example.test/{posting_id}",
        raw_text=f"Role {posting_id}",
        content_hash=(posting_id * 64)[:64],
        captured_at=now,
    )
    posting = Posting(
        id=posting_id,
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key=f"identity-{posting_id}",
        title=f"Role {posting_id}",
        company="Example",
        location="Remote",
        description="Test role",
        identity_status="verified",
        created_at=now,
    )
    session.add_all([source, posting])
    session.flush()
    return posting


def test_archived_application_delete_removes_only_application_owned_records(
    tmp_path,
) -> None:
    session = _session(tmp_path)
    now = datetime.now(UTC)
    try:
        posting = _add_posting(session, "posting-1")
        application = Application(
            id="application-1",
            posting_id=posting.id,
            status="archived",
            application_url="",
            resume_used="test.pdf",
            notes="test",
            created_at=now,
            updated_at=now,
        )
        session.add(application)
        session.flush()
        session.add_all(
            [
                ApplicationEvent(
                    id="event-1",
                    application_id=application.id,
                    event_type="application_archived",
                    from_status="submitted",
                    to_status="archived",
                    notes="",
                    occurred_at=now,
                ),
                Outcome(
                    id="outcome-1",
                    posting_id=posting.id,
                    application_id=application.id,
                    outcome_type="withdrawn_by_user",
                    stage_reached="submitted",
                    reason_code="",
                    notes="",
                    recorded_at=now,
                ),
                ApplicationTask(
                    id="task-1",
                    application_id=application.id,
                    title="Task",
                    notes="",
                    due_at=None,
                    status="open",
                    completed_at=None,
                    created_at=now,
                    updated_at=now,
                ),
                ApplicationInterview(
                    id="interview-1",
                    application_id=application.id,
                    interview_type="recruiter_screen",
                    scheduled_at=now,
                    timezone="UTC",
                    format_location="",
                    participants="",
                    preparation_notes="",
                    outcome_notes="",
                    status="scheduled",
                    completed_at=None,
                    created_at=now,
                    updated_at=now,
                ),
                ApplicationContact(
                    id="contact-1",
                    application_id=application.id,
                    name="Recruiter",
                    role="",
                    company="",
                    email="",
                    phone="",
                    linkedin_url="",
                    notes="",
                    created_at=now,
                    updated_at=now,
                ),
                ApplicationDocument(
                    id="document-1",
                    application_id=application.id,
                    document_type="resume",
                    title="Resume",
                    file_path="",
                    source_url="",
                    status="draft",
                    notes="",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.commit()

        result = delete_archived_application(session, application.id)

        assert result.deleted is True
        assert session.get(Application, application.id) is None
        assert session.get(Posting, posting.id) is not None
        assert session.get(SourceDocument, posting.source_document_id) is not None
        assert (
            session.scalar(
                select(ApplicationEvent).where(ApplicationEvent.application_id == application.id)
            )
            is None
        )
        assert (
            session.scalar(select(Outcome).where(Outcome.application_id == application.id)) is None
        )
    finally:
        session.close()


def test_active_application_cannot_be_permanently_deleted(tmp_path) -> None:
    session = _session(tmp_path)
    now = datetime.now(UTC)
    try:
        posting = _add_posting(session, "posting-active")
        application = Application(
            id="application-active",
            posting_id=posting.id,
            status="submitted",
            application_url="",
            resume_used="",
            notes="",
            created_at=now,
            updated_at=now,
        )
        session.add(application)
        session.commit()

        with pytest.raises(
            ValueError,
            match="Only an archived application",
        ):
            delete_archived_application(session, application.id)

        assert session.get(Application, application.id) is not None
    finally:
        session.close()


def test_pending_cleanup_archives_capture_only_batches_atomically(
    tmp_path,
    monkeypatch,
) -> None:
    session = _session(tmp_path)
    now = datetime.now(UTC)
    try:
        posting_1 = _add_posting(session, "pending-1")
        posting_2 = _add_posting(session, "pending-2")
        run = CaptureRun(
            id="capture-1",
            source="linkedin",
            mode="supervised_live",
            status="completed",
            search_url="https://example.test/jobs",
            warnings_json="[]",
            requested_item_limit=2,
            observed_item_count=2,
            stop_reason="submitted_batch_completed",
            started_at=now,
            completed_at=now,
        )
        session.add(run)
        session.flush()
        session.add(
            CapturePage(
                id="page-1",
                capture_run_id=run.id,
                page_number=1,
                visible_job_ids_json='["job-1", "job-2"]',
                next_control_present=False,
                next_control_enabled=False,
            )
        )
        session.add_all(
            [
                CaptureItem(
                    id="item-1",
                    capture_run_id=run.id,
                    source_job_id="job-1",
                    source_url="https://example.test/job-1",
                    title=posting_1.title,
                    company=posting_1.company,
                    location=posting_1.location,
                    detail_status="verified",
                    verification_reasons_json="[]",
                    source_document_id=posting_1.source_document_id,
                    posting_id=posting_1.id,
                ),
                CaptureItem(
                    id="item-2",
                    capture_run_id=run.id,
                    source_job_id="job-2",
                    source_url="https://example.test/job-2",
                    title=posting_2.title,
                    company=posting_2.company,
                    location=posting_2.location,
                    detail_status="verified",
                    verification_reasons_json="[]",
                    source_document_id=posting_2.source_document_id,
                    posting_id=posting_2.id,
                ),
            ]
        )
        session.commit()

        calls = 0

        def fake_index(_session):
            nonlocal calls
            calls += 1
            if calls == 1:
                return [
                    SimpleNamespace(posting_id=posting_1.id),
                    SimpleNamespace(posting_id=posting_2.id),
                ]
            return []

        monkeypatch.setattr(
            "jolt.pending_inbox_cleanup.list_opportunity_index",
            fake_index,
        )

        result = clear_pending_review_inbox(session)

        session.refresh(run)
        assert result.pending_before == 2
        assert result.pending_after == 0
        assert result.cleared_pending_count == 2
        assert result.archived_capture_run_count == 1
        assert run.status == "archived"
        assert session.get(CaptureItem, "item-1") is not None
        assert session.get(Posting, posting_1.id) is not None
    finally:
        session.close()
