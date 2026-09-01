from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from jolt.ai_exchange_contract import (
    AIExchangeFeedbackItem,
    AIExchangeOutput,
    AIExchangeScope,
)
from jolt.database import (
    CaptureRun,
    Posting,
    SourceDocument,
    create_session_factory,
)
from jolt.global_context import GlobalAIContextOverlay
from jolt.market_intelligence_exchange import (
    build_market_intelligence_exchange,
    import_market_intelligence_exchange,
)
from jolt.market_preparation_import import (
    MarketPreparationImportRecord,
    MarketPreparationImportResponse,
)


def test_market_exchange_exports_evidence_without_local_judgments(tmp_path, monkeypatch) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    source = SourceDocument(
        id="market-source-1",
        source_type="linkedin",
        source_url="https://www.linkedin.com/jobs/view/999/",
        raw_text="Technical Support Engineer\nExample\nSpain Remote\nWindows SQL API support",
        content_hash="c" * 64,
        captured_at=now,
    )
    posting = Posting(
        id="market-posting-1",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key="linkedin:999",
        title="Technical Support Engineer",
        company="Example",
        location="Spain · Remote",
        description=source.raw_text,
        identity_status="verified",
        created_at=now,
    )
    capture = CaptureRun(
        id="market-capture-1",
        source="linkedin",
        mode="supervised_live",
        status="completed",
        search_url="https://www.linkedin.com/jobs/search/?keywords=technical+support",
        warnings_json="[]",
        requested_item_limit=25,
        observed_item_count=1,
        stop_reason="requested_limit_reached",
        started_at=now,
        completed_at=now,
    )
    session.add_all([source, capture])
    session.flush()
    session.add(posting)
    session.commit()

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
    assert exchange.context_version and exchange.context_version.startswith("global-context-")
    assert exchange.evidence["counts"] == {"jobs": 1, "capture_runs": 1}
    job = exchange.evidence["jobs"][0]
    assert job["posting_id"] == posting.id
    assert "Windows SQL API support" in job["evidence_text"]
    serialized = json.dumps(exchange.evidence).casefold()
    assert '"recommendation"' not in serialized
    assert '"ranking_score"' not in serialized
    assert '"confidence"' not in serialized
    assert '"evaluation_reasons"' not in serialized


def test_market_exchange_import_updates_ai_context_and_reviewable_actions(monkeypatch) -> None:
    saved: list[GlobalAIContextOverlay] = []
    imported = []
    monkeypatch.setattr(
        "jolt.market_intelligence_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    monkeypatch.setattr(
        "jolt.market_intelligence_exchange.save_global_ai_context",
        lambda context: saved.append(context) or context,
    )

    def fake_import(request):
        imported.append(request)
        record = MarketPreparationImportRecord(
            id="market-import-1",
            source=request.source,
            summary=request.summary,
            imported_at=datetime.now(UTC).isoformat(),
            action_count=len(request.market_recommendations),
            actions=request.market_recommendations,
            raw_payload=request.raw_payload,
        )
        return MarketPreparationImportResponse(imported_count=record.action_count, latest_import=record)

    monkeypatch.setattr("jolt.market_intelligence_exchange.import_market_preparation", fake_import)

    output = AIExchangeOutput(
        exchange_id="market-exchange-1",
        reviewed_at=datetime.now(UTC),
        review_version="market-v1",
        scope=AIExchangeScope(
            section="market_insights",
            analysis_types=["market_signal", "gap_signal", "recommendation", "context_update"],
        ),
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="recommendation",
                entity_type="market",
                entity_id="target-search",
                payload={
                    "title": "Prioritize application support",
                    "rationale": "Repeated SQL/API demand across target roles.",
                    "proposed_action": "Increase Application Support searches.",
                    "priority": "high",
                },
                confidence=90,
                evidence_refs=["posting:1", "posting:2"],
            )
        ],
        context_patch={
            "market_summary": {"dominant_role_family": "Application Support"},
            "skills_gap_summary": {"recurring": ["SQL", "REST API"]},
        },
        summary={"executive_summary": "Application Support remains the strongest target."},
    )

    response = import_market_intelligence_exchange(output)

    assert response.preparation.imported_count == 1
    assert saved[0].market_summary["dominant_role_family"] == "Application Support"
    assert saved[0].skills_gap_summary["recurring"] == ["SQL", "REST API"]
    assert imported[0].market_recommendations[0].priority == "high"
    assert imported[0].summary == "Application Support remains the strongest target."


def test_market_exchange_import_rejects_user_owned_patch(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.market_intelligence_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    output = AIExchangeOutput(
        exchange_id="market-exchange-invalid",
        reviewed_at=datetime.now(UTC),
        review_version="market-v1",
        scope=AIExchangeScope(section="market_insights", analysis_types=["context_update"]),
        context_patch={"job_search_preferences": {"languages": ["German"]}},
    )

    with pytest.raises(ValueError, match="non-patchable"):
        import_market_intelligence_exchange(output)
