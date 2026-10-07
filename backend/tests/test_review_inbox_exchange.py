from __future__ import annotations

import json
from datetime import UTC, datetime

from jolt.database import CaptureItem, CaptureRun, Posting, SourceDocument, create_session_factory
from jolt.review_inbox_exchange import (
    build_current_review_inbox_bundle,
    build_review_inbox_exchange_json,
)


def test_review_inbox_exchange_adds_reasoning_context_without_local_decisions(
    tmp_path, monkeypatch
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    session = create_session_factory(database_url)()
    now = datetime.now(UTC)

    source = SourceDocument(
        id="source-review-exchange",
        source_type="linkedin",
        source_url="https://www.linkedin.com/jobs/view/777/",
        raw_text="Support Engineer\nExample\nSpain Remote\nWindows and Microsoft 365 support",
        content_hash="b" * 64,
        captured_at=now,
    )
    posting = Posting(
        id="posting-review-exchange",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key="linkedin:777",
        title="Support Engineer",
        company="Example",
        location="Spain · Remote",
        description=source.raw_text,
        identity_status="verified",
        created_at=now,
    )
    capture = CaptureRun(
        id="capture-review-exchange",
        source="linkedin",
        mode="supervised_live",
        status="completed",
        search_url="https://www.linkedin.com/jobs/search/",
        warnings_json="[]",
        requested_item_limit=1,
        observed_item_count=1,
        stop_reason="requested_limit_reached",
        started_at=now,
        completed_at=now,
    )
    item = CaptureItem(
        id="item-review-exchange",
        capture_run_id=capture.id,
        source_job_id="777",
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
    session.add(item)
    session.commit()

    monkeypatch.setattr(
        "jolt.review_inbox_exchange.build_global_context_snapshot",
        lambda: {
            "job_search_preferences": {"languages": ["English", "Spanish"]},
            "ai_context": {"market_summary": {"signal": "sample"}},
            "ownership": {},
        },
    )

    try:
        payload = json.loads(build_review_inbox_exchange_json(session))
    finally:
        session.close()

    assert payload["exchange_section"] == "review_inbox"
    assert payload["context_version"].startswith("global-context-")
    assert payload["reasoning_context"]["job_search_preferences"]["languages"] == [
        "English",
        "Spanish",
    ]
    assert payload["classification_authority"] == "external_ai"
    assert payload["jolt_decisions_included"] is False
    assert payload["jolt_scores_included"] is False
    assert payload["response_template"]["review_source"] == "chatgpt_source_first"
    assert payload["context_ownership"]["human_review_decisions"] == "protected"

    instructions = payload["reasoning_instructions"]
    assert instructions["processing_mode"] == "strict_sequential_per_job"
    assert instructions["sequential_review_protocol"][0] == (
        "Process jobs in jobs[] order, one vacancy at a time."
    )
    assert any(
        "Do not compare, rank, shortlist, or aggregate" in step
        for step in instructions["sequential_review_protocol"]
    )
    assert "hardline_reject is true" in instructions["deterministic_location_authority"]
    assert any(
        "every current jobs[] posting_id appears exactly once" in step
        for step in instructions["post_review_self_audit"]
    )
    assert "after all per-job reviews" in instructions["aggregation_rule"]
    assert "informational only" in instructions["schedule_rule"]
    assert "minimum number of real-world years" in instructions["professional_refresh_rule"]
    assert "Do not hard-reject merely because" in instructions["mandatory_experience_rule"]


def test_current_review_inbox_bundle_preserves_multiple_capture_runs(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'multi.db').as_posix()}"
    session = create_session_factory(database_url)()
    now = datetime.now(UTC)

    for index, source_name in enumerate(("linkedin", "indeed"), start=1):
        source = SourceDocument(
            id=f"source-multi-{index}",
            source_type=source_name,
            source_url=f"https://example.com/job/{index}",
            raw_text=f"Support Engineer {index}\nExample {index}\nLocation: Spain\nSupport work",
            content_hash=str(index) * 64,
            captured_at=now,
        )
        posting = Posting(
            id=f"posting-multi-{index}",
            source_document_id=source.id,
            canonical_url=source.source_url,
            identity_key=f"url:{source.source_url}",
            title=f"Support Engineer {index}",
            company=f"Example {index}",
            location="Spain",
            description=source.raw_text,
            identity_status="new",
            created_at=now,
        )
        capture = CaptureRun(
            id=f"capture-multi-{index}",
            source=source_name,
            mode="supervised_live",
            status="completed",
            search_url=f"https://example.com/search/{index}",
            warnings_json="[]",
            requested_item_limit=1,
            observed_item_count=1,
            stop_reason="requested_limit_reached",
            started_at=now,
            completed_at=now,
        )
        item = CaptureItem(
            id=f"item-multi-{index}",
            capture_run_id=capture.id,
            source_job_id=f"job-{index}",
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
        session.add(item)

    session.commit()
    try:
        payload = build_current_review_inbox_bundle(session)
    finally:
        session.close()

    assert payload["pack_type"] == "jolt_ai_review_bundle_input"
    assert payload["counts"]["capture_runs"] == 2
    assert payload["counts"]["capture_items"] == 2
    assert {job["posting_id"] for job in payload["jobs"]} == {
        "posting-multi-1",
        "posting-multi-2",
    }
    assert len(payload["review_groups"]) == 2
    assert len(payload["response_template"]["reviews"]) == 2
