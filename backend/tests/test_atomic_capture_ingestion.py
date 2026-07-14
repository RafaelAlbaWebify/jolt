from __future__ import annotations

import pytest
from sqlalchemy import func, select

from jolt import live_capture_workflow
from jolt.database import (
    CaptureItem,
    CapturePage,
    CaptureRun,
    Evaluation,
    Posting,
    SourceDocument,
    create_session_factory,
)
from jolt.schemas import LinkedInLiveCaptureItemRequest, LinkedInLiveCaptureRequest


def test_live_capture_rolls_back_all_rows_when_one_item_fails(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{(tmp_path / 'atomic.db').as_posix()}"
    factory = create_session_factory(database_url)
    original = live_capture_workflow.ingest_capture_item
    calls = 0

    def fail_on_second_item(session, request):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated second-item failure")
        return original(session, request)

    monkeypatch.setattr(live_capture_workflow, "ingest_capture_item", fail_on_second_item)
    request = LinkedInLiveCaptureRequest(
        search_url="https://www.linkedin.com/jobs/search/",
        items=[
            LinkedInLiveCaptureItemRequest(
                source_job_id="job-1",
                source_url="https://www.linkedin.com/jobs/view/job-1",
                title="Application Support Engineer",
                company="Example One",
                location="Spain",
                description="Application support, SQL, incidents and integrations.",
                identity_verified=True,
                verification_reason="detail identity matched",
            ),
            LinkedInLiveCaptureItemRequest(
                source_job_id="job-2",
                source_url="https://www.linkedin.com/jobs/view/job-2",
                title="Production Support Engineer",
                company="Example Two",
                location="Spain",
                description="Production support, APIs and incident ownership.",
                identity_verified=True,
                verification_reason="detail identity matched",
            ),
        ],
    )

    with factory() as session, pytest.raises(RuntimeError, match="second-item failure"):
        live_capture_workflow.run_linkedin_live_capture(session, request)

    with factory() as verification_session:
        for model in (CaptureRun, CapturePage, CaptureItem, SourceDocument, Posting, Evaluation):
            count = verification_session.scalar(select(func.count()).select_from(model))
            assert count == 0
