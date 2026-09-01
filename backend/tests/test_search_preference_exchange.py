from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jolt.ai_exchange_contract import (
    AIExchangeFeedbackItem,
    AIExchangeOutput,
    AIExchangeScope,
)
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord
from jolt.database import Posting, SourceDocument, create_session_factory
from jolt.global_context import GlobalAIContextOverlay
from jolt.job_search_preferences import JobSearchPreferences
from jolt.market_preparation_import import (
    MarketPreparationImportRecord,
    MarketPreparationImportResponse,
)
from jolt.search_preference_exchange import (
    build_search_preference_exchange,
    import_search_preference_exchange,
)


def test_search_exchange_exports_preferences_as_protected_evidence(tmp_path, monkeypatch) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    source = SourceDocument(
        id="search-source-1",
        source_type="linkedin",
        source_url="https://example.com/job/1",
        raw_text="Application Support Engineer\nRemote Europe\nSQL and API troubleshooting",
        content_hash="a" * 64,
        captured_at=now,
    )
    posting = Posting(
        id="search-posting-1",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key="search:1",
        title="Application Support Engineer",
        company="Example",
        location="Remote Europe",
        description=source.raw_text,
        identity_status="verified",
        created_at=now,
    )
    session.add(source)
    session.flush()
    session.add(posting)
    session.commit()
    monkeypatch.setattr(
        "jolt.search_preference_exchange.build_global_context_snapshot",
        lambda: {"job_search_preferences": {}, "ai_context": {}, "ownership": {}},
    )
    monkeypatch.setattr(
        "jolt.search_preference_exchange.load_job_search_preferences",
        lambda: JobSearchPreferences(languages=["English", "Spanish"]),
    )

    try:
        exchange = build_search_preference_exchange(session)
    finally:
        session.close()

    assert exchange.scope.section == "search_preferences"
    assert exchange.evidence["current_preferences"]["languages"] == ["English", "Spanish"]
    assert exchange.evidence["counts"]["postings"] == 1
    assert "SQL and API troubleshooting" in exchange.evidence["postings"][0]["evidence_text"]
    assert "job_search_preferences" in exchange.protected_state["non_patchable"]
    assert exchange.protected_state["patchable_context_namespaces"] == [
        "audit_summary",
        "capture_strategy",
    ]


def test_search_exchange_import_creates_pending_search_improvement_without_saving_preferences(
    monkeypatch,
) -> None:
    saved_context: list[GlobalAIContextOverlay] = []
    saved_feedback: list[AIExchangeOutput] = []
    imported = []
    monkeypatch.setattr(
        "jolt.search_preference_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    monkeypatch.setattr(
        "jolt.search_preference_exchange.save_global_ai_context",
        lambda context: saved_context.append(context) or context,
    )
    monkeypatch.setattr(
        "jolt.search_preference_exchange.save_ai_exchange_feedback",
        lambda output: (
            saved_feedback.append(output)
            or AIExchangeFeedbackRecord(
                id="feedback-1",
                exchange_id=output.exchange_id,
                section=output.scope.section,
                review_version=output.review_version,
                reviewed_at=output.reviewed_at,
                imported_at=datetime.now(UTC),
                feedback=output.feedback,
                summary=output.summary,
            )
        ),
    )

    def fake_import(request):
        imported.append(request)
        actions = request.search_filter_improvements
        record = MarketPreparationImportRecord(
            id="search-prep-1",
            source=request.source,
            summary=request.summary,
            imported_at=datetime.now(UTC).isoformat(),
            action_count=len(actions),
            actions=actions,
            raw_payload=request.raw_payload,
        )
        return MarketPreparationImportResponse(imported_count=len(actions), latest_import=record)

    monkeypatch.setattr("jolt.search_preference_exchange.import_market_preparation", fake_import)
    output = AIExchangeOutput(
        exchange_id="search-exchange-1",
        reviewed_at=datetime.now(UTC),
        review_version="search-v1",
        scope=AIExchangeScope(
            section="search_preferences",
            analysis_types=["recommendation", "context_update"],
        ),
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="recommendation",
                entity_type="search_strategy",
                entity_id="titles",
                payload={
                    "action_type": "target_title",
                    "title": "Add Application Support Analyst",
                    "rationale": "Repeated relevant vacancies use analyst wording.",
                    "proposed_action": "Review adding Application Support Analyst to target titles.",
                    "priority": "high",
                },
                evidence_refs=["posting:1", "posting:2"],
            )
        ],
        context_patch={
            "capture_strategy": {"title_expansion_candidate": "Application Support Analyst"}
        },
        summary={
            "executive_summary": "Broaden title coverage without changing preferences automatically."
        },
    )

    response = import_search_preference_exchange(output)

    assert saved_context[0].capture_strategy["title_expansion_candidate"] == (
        "Application Support Analyst"
    )
    assert saved_feedback == [output]
    assert response.preparation.imported_count == 1
    action = imported[0].search_filter_improvements[0]
    assert action.status == "pending"
    assert action.action_type == "target_title"
    assert "posting:1" in action.rationale


def test_search_exchange_rejects_direct_job_preference_patch(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.search_preference_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    output = AIExchangeOutput(
        exchange_id="search-invalid",
        reviewed_at=datetime.now(UTC),
        review_version="search-v1",
        scope=AIExchangeScope(section="search_preferences", analysis_types=["context_update"]),
        context_patch={"job_search_preferences": {"languages": ["German"]}},
    )

    with pytest.raises(ValueError, match="non-patchable"):
        import_search_preference_exchange(output)
