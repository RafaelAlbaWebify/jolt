from __future__ import annotations

import json

from sqlalchemy import select

from jolt.ai_review_pack import build_ai_review_json
from jolt.database import CaptureItem, CaptureRun, create_session_factory
from jolt.schemas import ManualIntakeRequest
from jolt.workflow import ingest_manual


def test_manual_intake_enters_existing_ai_review_contract(tmp_path) -> None:
    database_url=f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    factory=create_session_factory(database_url)
    with factory() as session:
        intake=ingest_manual(session, ManualIntakeRequest(source_url="https://example.com/jobs/42", raw_text="Application Support Engineer\nExample Systems\nLocation: Remote\nTroubleshoot SQL, logs and APIs."))
        run=session.scalar(select(CaptureRun).where(CaptureRun.source == "manual"))
        assert run is not None
        assert run.mode == "manual_intake"
        item=session.scalar(select(CaptureItem).where(CaptureItem.capture_run_id == run.id))
        assert item is not None
        assert item.detail_status == "verified"
        assert item.posting_id == intake.posting_id
        review_input=json.loads(build_ai_review_json(session))
        assert review_input["capture_run_id"] == run.id
        assert review_input["capture"]["source"] == "manual"
        assert review_input["capture"]["mode"] == "manual_intake"
        assert review_input["counts"]["capture_items"] == 1
        assert review_input["jobs"][0]["posting_id"] == intake.posting_id
        assert review_input["jobs"][0]["source_job_id"].startswith("manual:")


def test_duplicate_manual_intake_does_not_create_duplicate_reasoning_batch(tmp_path) -> None:
    database_url=f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    factory=create_session_factory(database_url)
    payload=ManualIntakeRequest(source_url="https://example.com/jobs/duplicate", raw_text="Support Engineer\nExample Systems\nLocation: Remote\nSupport APIs.")
    with factory() as session:
        first=ingest_manual(session,payload)
        second=ingest_manual(session,payload)
        assert first.identity_status == "new"
        assert second.identity_status == "confirmed_duplicate"
        runs=list(session.scalars(select(CaptureRun).where(CaptureRun.source == "manual")).all())
        assert len(runs) == 1
        items=list(session.scalars(select(CaptureItem).where(CaptureItem.capture_run_id == runs[0].id)).all())
        assert len(items) == 1
