from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

from jolt.ai_review_pack import build_ai_review_json, build_ai_review_pack
from jolt.database import (
    CaptureItem,
    CapturePage,
    CaptureRun,
    Posting,
    SourceDocument,
    create_session_factory,
)


def _seed_ai_review_capture(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    factory = create_session_factory(database_url)
    session = factory()
    now = datetime.now(UTC)
    raw_text = (
        "Technical Support Engineer\n"
        "Example Systems\n"
        "Location: Spain Remote\n"
        "Troubleshoot Windows, SQL, logs and REST APIs.\n"
        "Job search faster with Premium\n"
        "Promotional LinkedIn material that must not reach analysis."
    )

    source = SourceDocument(
        id="source-ai-1",
        source_type="linkedin",
        source_url="https://www.linkedin.com/jobs/view/123/",
        raw_text=raw_text,
        content_hash="a" * 64,
        captured_at=now,
    )
    posting = Posting(
        id="posting-ai-1",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key="linkedin:123",
        title="Technical Support Engineer",
        company="Example Systems",
        location="Spain · Remote",
        description=raw_text,
        identity_status="verified",
        created_at=now,
    )
    capture = CaptureRun(
        id="capture-ai-1",
        source="linkedin",
        mode="supervised_live",
        status="completed",
        search_url="https://www.linkedin.com/jobs/search/",
        warnings_json="[]",
        requested_item_limit=25,
        observed_item_count=1,
        stop_reason="no_next_page",
        started_at=now,
        completed_at=now,
    )
    page = CapturePage(
        id="page-ai-1",
        capture_run_id=capture.id,
        page_number=1,
        visible_job_ids_json='["123"]',
        next_control_present=False,
        next_control_enabled=False,
    )
    item = CaptureItem(
        id="item-ai-1",
        capture_run_id=capture.id,
        source_job_id="123",
        source_url=source.source_url,
        title=posting.title,
        company=posting.company,
        location=posting.location,
        detail_status="verified",
        verification_reasons_json="[]",
        source_document_id=source.id,
        posting_id=posting.id,
    )

    session.add_all([source, capture])
    session.flush()
    session.add(posting)
    session.flush()
    session.add_all([page, item])
    session.commit()
    return session, capture, posting, raw_text


def _assert_clean_job(job: dict[str, object], posting: Posting, raw_text: str) -> None:
    assert job["posting_id"] == posting.id
    assert job["source_job_id"] == "123"
    assert job["title"] == posting.title
    assert job["company"] == posting.company
    assert "Troubleshoot Windows" in str(job["analysis_text"])
    assert "Job search faster with Premium" not in str(job["analysis_text"])
    assert "Promotional LinkedIn material" not in str(job["analysis_text"])

    audit = job["audit"]
    assert isinstance(audit, dict)
    assert audit["source_raw_text"] == raw_text
    assert audit["source_raw_text_sha256"]

    serialized = json.dumps(job).casefold()
    assert '"recommendation"' not in serialized
    assert '"ranking_score"' not in serialized
    assert '"eligibility"' not in serialized
    assert '"confidence"' not in serialized
    assert '"engine_version"' not in serialized
    assert '"evaluation_id"' not in serialized


def test_ai_review_pack_contains_clean_evidence_but_no_jolt_decisions(tmp_path) -> None:
    session, capture, posting, raw_text = _seed_ai_review_capture(tmp_path)
    try:
        payload = build_ai_review_pack(session)
        with ZipFile(BytesIO(payload)) as archive:
            names = set(archive.namelist())
            assert names == {
                "README.md",
                "capture/pages.json",
                "capture/run.json",
                "contract/ai_review_response_template.json",
                "jobs/ai_review_jobs.json",
                "manifest.json",
            }
            manifest = json.loads(archive.read("manifest.json"))
            jobs = json.loads(archive.read("jobs/ai_review_jobs.json"))
            template = json.loads(archive.read("contract/ai_review_response_template.json"))

        assert manifest["pack_type"] == "jolt_ai_review_input"
        assert manifest["capture_run_id"] == capture.id
        assert manifest["classification_authority"] == "external_ai"
        assert manifest["jolt_decisions_included"] is False
        assert manifest["jolt_scores_included"] is False
        _assert_clean_job(jobs[0], posting, raw_text)
        assert template["capture_run_id"] == capture.id
        assert template["review_source"] == "chatgpt_source_first"
    finally:
        session.close()


def test_ai_review_json_is_self_contained_and_matches_review_contract(tmp_path) -> None:
    session, capture, posting, raw_text = _seed_ai_review_capture(tmp_path)
    try:
        document = json.loads(build_ai_review_json(session))

        assert document["pack_type"] == "jolt_ai_review_input"
        assert document["pack_version"] == "1.0"
        assert document["review_contract_version"] == "1.0"
        assert document["capture_run_id"] == capture.id
        assert document["classification_authority"] == "external_ai"
        assert document["jolt_decisions_included"] is False
        assert document["jolt_scores_included"] is False
        assert document["counts"] == {
            "capture_pages": 1,
            "capture_items": 1,
            "verified_items": 1,
        }
        assert document["capture"]["capture_run_id"] == capture.id
        assert document["pages"][0]["visible_job_ids"] == ["123"]
        _assert_clean_job(document["jobs"][0], posting, raw_text)
        assert document["response_template"]["capture_run_id"] == capture.id
        assert document["response_template"]["review_source"] == "chatgpt_source_first"
    finally:
        session.close()
