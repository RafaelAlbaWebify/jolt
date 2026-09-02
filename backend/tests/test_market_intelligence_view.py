from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jolt.ai_exchange_contract import AIExchangeFeedbackItem
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackIndex, AIExchangeFeedbackRecord
from jolt.database import CaptureRun, MarketIntelligenceObservation, create_session_factory
from jolt.global_context import GlobalAIContextOverlay
from jolt.market_intelligence_view import build_market_intelligence_view


def _observation(*, suffix: str, captured_at: datetime, identity_key: str) -> MarketIntelligenceObservation:
    return MarketIntelligenceObservation(
        id=f"observation-{suffix}",
        source_capture_run_id=f"capture-{suffix}",
        source_job_id=suffix,
        posting_identity_key=identity_key,
        source_url=f"https://example.test/jobs/{suffix}",
        title="Technical Support Engineer",
        company="Example",
        location="Remote",
        description="Verified market evidence",
        engine_version="",
        recommendation="",
        confidence="",
        ranking_score=None,
        reasons_json="[]",
        captured_at=captured_at,
        observed_at=captured_at,
    )


def test_market_view_uses_ai_context_and_marks_newer_capture_stale(tmp_path, monkeypatch) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    session.add_all(
        [
            CaptureRun(
                id="capture-latest",
                source="linkedin",
                mode="supervised_live",
                status="completed",
                search_url="https://example.test/search",
                warnings_json="[]",
                requested_item_limit=2,
                observed_item_count=2,
                stop_reason="requested_limit_reached",
                started_at=now,
                completed_at=now,
            ),
            _observation(suffix="1", captured_at=now - timedelta(minutes=5), identity_key="role:a"),
            _observation(suffix="2", captured_at=now - timedelta(minutes=4), identity_key="role:a"),
        ]
    )
    session.commit()

    context = GlobalAIContextOverlay(
        updated_at=now - timedelta(hours=1),
        updated_by="chatgpt:test",
        market_summary={"executive_summary": "Application support demand is strong."},
        skills_gap_summary={"priority": ["SQL", "API"]},
    )
    feedback_record = AIExchangeFeedbackRecord(
        id="feedback-record",
        exchange_id="market-exchange",
        section="market_insights",
        review_version="market-v1",
        reviewed_at=now - timedelta(hours=1),
        imported_at=now - timedelta(hours=1),
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="market_signal",
                entity_type="market",
                entity_id="signal",
                payload={"signal": "API demand recurring"},
            ),
            AIExchangeFeedbackItem(
                feedback_type="recommendation",
                entity_type="market",
                entity_id="recommendation",
                payload={
                    "title": "Build API evidence",
                    "proposed_action": "Create one API troubleshooting exercise.",
                },
            ),
        ],
    )
    monkeypatch.setattr("jolt.market_intelligence_view.load_global_ai_context", lambda: context)
    monkeypatch.setattr(
        "jolt.market_intelligence_view.list_ai_exchange_feedback",
        lambda section: AIExchangeFeedbackIndex(total_import_count=1, records=[feedback_record]),
    )
    monkeypatch.setattr(
        "jolt.market_intelligence_view.global_context_version",
        lambda: "global-context-test",
    )

    try:
        view = build_market_intelligence_view(session)
    finally:
        session.close()

    assert view.authority == "chatgpt"
    assert view.context_version == "global-context-test"
    assert view.market_summary["executive_summary"] == "Application support demand is strong."
    assert view.evidence_provenance.observation_count == 2
    assert view.evidence_provenance.canonical_role_count == 1
    assert view.evidence_provenance.duplicate_observation_count == 1
    assert view.freshness.status == "stale"
    assert view.freshness.needs_analysis is True
    assert len(view.latest_feedback) == 2
    assert len(view.recommendations) == 1
    assert view.recommendations[0].entity_id == "recommendation"


def test_market_view_is_current_when_ai_analysis_is_newer_than_capture(tmp_path, monkeypatch) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    session.add(
        CaptureRun(
            id="capture-current",
            source="linkedin",
            mode="supervised_live",
            status="completed",
            search_url="https://example.test/search",
            warnings_json="[]",
            requested_item_limit=1,
            observed_item_count=1,
            stop_reason="requested_limit_reached",
            started_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=2),
        )
    )
    session.commit()
    monkeypatch.setattr(
        "jolt.market_intelligence_view.load_global_ai_context",
        lambda: GlobalAIContextOverlay(
            updated_at=now,
            updated_by="chatgpt:test",
            market_summary={"status": "analyzed"},
        ),
    )
    monkeypatch.setattr(
        "jolt.market_intelligence_view.list_ai_exchange_feedback",
        lambda section: AIExchangeFeedbackIndex(total_import_count=0, records=[]),
    )
    monkeypatch.setattr(
        "jolt.market_intelligence_view.global_context_version",
        lambda: "global-context-test",
    )

    try:
        view = build_market_intelligence_view(session)
    finally:
        session.close()

    assert view.freshness.status == "current"
    assert view.freshness.needs_analysis is False
