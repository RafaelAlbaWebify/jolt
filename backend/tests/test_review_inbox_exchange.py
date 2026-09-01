from __future__ import annotations

import json
from datetime import UTC, datetime

from jolt.database import CaptureItem, CaptureRun, Posting, SourceDocument, create_session_factory
from jolt.review_inbox_exchange import build_review_inbox_exchange_json


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
