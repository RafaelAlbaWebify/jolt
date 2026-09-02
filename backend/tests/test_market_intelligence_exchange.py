from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from jolt.ai_exchange_contract import AIExchangeFeedbackItem, AIExchangeOutput, AIExchangeScope
from jolt.database import CaptureItem, CaptureRun, Posting, SourceDocument, create_session_factory
from jolt.global_context import GlobalAIContextOverlay
from jolt.market_intelligence_exchange import (
    build_market_intelligence_exchange,
    import_market_intelligence_exchange,
)


def _add_market_evidence(
    session,
    *,
    suffix: str,
    captured_at: datetime,
    source_text: str,
    posting_text: str,
) -> None:
    source = SourceDocument(
        id=f"market-source-{suffix}",
        source_type="linkedin",
        source_url=f"https://www.linkedin.com/jobs/view/{suffix}/",
        raw_text=source_text,
        content_hash=(suffix[0] if suffix else "c") * 64,
        captured_at=captured_at,
    )
    capture = CaptureRun(
        id=f"market-capture-{suffix}",
        source="linkedin",
        mode="supervised_live",
        status="completed",
        search_url="https://www.linkedin.com/jobs/search/?keywords=technical+support",
        warnings_json="[]",
        requested_item_limit=25,
        observed_item_count=1,
        stop_reason="requested_limit_reached",
        started_at=captured_at,
        completed_at=captured_at,
    )
    session.add_all([source, capture])
    session.flush()
    posting = Posting(
        id=f"market-posting-{suffix}",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key=f"linkedin:{suffix}",
        title="Technical Support Engineer",
        company="Example",
        location="Remote",
        description=posting_text,
        identity_status="verified",
        created_at=captured_at,
    )
    session.add(posting)
    session.flush()
    session.add(
        CaptureItem(
            id=f"market-item-{suffix}",
            capture_run_id=capture.id,
            source_job_id=suffix,
            source_url=source.source_url,
            title="Technical Support Engineer",
            company="Example",
            location="Remote",
            detail_status="verified",
            verification_reasons_json="[]",
            source_document_id=source.id,
            posting_id=posting.id,
        )
    )
    session.commit()


def test_market_exchange_exports_current_source_evidence_without_local_judgments(
    tmp_path, monkeypatch
) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    _add_market_evidence(
        session,
        suffix="999",
        captured_at=now,
        source_text="CURRENT verified source evidence\nWindows SQL API support",
        posting_text="STALE canonical posting description that must not drive the exchange",
    )
    _add_market_evidence(
        session,
        suffix="888",
        captured_at=now - timedelta(days=120),
        source_text="OLD evidence outside the market corpus window",
        posting_text="OLD canonical posting text",
    )

    monkeypatch.setattr(
        "jolt.market_intelligence_exchange.build_global_context_snapshot",
        lambda: {
            "job_search_preferences": {"languages": ["English", "Spanish"]},
            "ai_context": {},
            "ownership": {},
        },
    )

    try:
        exchange = build_market_intelligence_exchange(session)
    finally:
        session.close()

    assert exchange.scope.section == "market_insights"
    assert exchange.evidence["counts"] == {"jobs": 1, "capture_runs": 1}
    assert exchange.evidence["corpus_policy"]["window_days"] == 90
    assert exchange.evidence["corpus_policy"]["max_verified_observations"] == 500
    job = exchange.evidence["jobs"][0]
    assert job["source_job_id"] == "999"
    assert job["posting_identity_key"] == "linkedin:999"
    assert "CURRENT verified source evidence" in job["evidence_text"]
    assert "STALE canonical posting description" not in job["evidence_text"]
    serialized = json.dumps(exchange.evidence).casefold()
    assert "old evidence outside" not in serialized
    assert '"recommendation"' not in serialized
    assert '"ranking_score"' not in serialized
    assert '"confidence"' not in serialized
    assert '"evaluation_reasons"' not in serialized


def test_market_exchange_import_persists_signals_but_counts_only_recommendations(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "jolt.ai_exchange_feedback_store._data_path",
        lambda: tmp_path / "ai_exchange_feedback.json",
    )
    monkeypatch.setattr(
        "jolt.market_intelligence_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    output = AIExchangeOutput(
        exchange_id="market-exchange-1",
        reviewed_at=datetime.now(UTC),
        review_version="market-v1",
        scope=AIExchangeScope(
            section="market_insights",
            analysis_types=["market_signal", "gap_signal", "recommendation"],
        ),
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="market_signal",
                entity_type="market",
                entity_id="signal-1",
                payload={"signal": "API demand is recurring"},
                confidence=90,
            ),
            AIExchangeFeedbackItem(
                feedback_type="recommendation",
                entity_type="market",
                entity_id="action-1",
                payload={
                    "title": "Strengthen API troubleshooting",
                    "rationale": "Repeated demand across target roles.",
                    "proposed_action": "Build one API troubleshooting portfolio exercise.",
                    "priority": "high",
                },
                confidence=92,
            ),
        ],
        context_patch={},
        summary={"executive_summary": "API support demand is recurring."},
    )

    response = import_market_intelligence_exchange(output)

    assert response.recommendation_count == 1
    assert len(response.feedback_record.feedback) == 2
    assert response.feedback_record.feedback[0].feedback_type == "market_signal"
    assert response.feedback_record.feedback[1].feedback_type == "recommendation"


def test_market_exchange_import_rejects_section_context_patch() -> None:
    output = AIExchangeOutput(
        exchange_id="market-exchange-invalid",
        reviewed_at=datetime.now(UTC),
        review_version="market-v1",
        scope=AIExchangeScope(section="market_insights", analysis_types=["context_update"]),
        context_patch={"market_summary": {"role": "Application Support"}},
    )

    with pytest.raises(ValueError, match="top-level context_patch"):
        import_market_intelligence_exchange(output)


def test_market_exchange_import_rejects_malformed_recommendation() -> None:
    output = AIExchangeOutput(
        exchange_id="market-exchange-invalid-recommendation",
        reviewed_at=datetime.now(UTC),
        review_version="market-v1",
        scope=AIExchangeScope(section="market_insights", analysis_types=["recommendation"]),
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="recommendation",
                entity_type="market",
                entity_id="bad-action",
                payload={"title": "", "proposed_action": ""},
            )
        ],
    )

    with pytest.raises(ValueError, match="non-empty title"):
        import_market_intelligence_exchange(output)
