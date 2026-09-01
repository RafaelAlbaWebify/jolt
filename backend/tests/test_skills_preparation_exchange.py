from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from jolt.ai_exchange_contract import (
    AIExchangeFeedbackItem,
    AIExchangeOutput,
    AIExchangeScope,
)
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord
from jolt.database import (
    LinkedInPresenceCapture,
    Posting,
    SourceDocument,
    create_session_factory,
)
from jolt.global_context import GlobalAIContextOverlay
from jolt.market_preparation_import import (
    MarketPreparationImportRecord,
    MarketPreparationImportResponse,
)
from jolt.skills_preparation_exchange import (
    build_skills_preparation_exchange,
    import_skills_preparation_exchange,
)


def test_skills_exchange_exports_raw_evidence_without_local_gap_judgments(
    tmp_path, monkeypatch
) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    source = SourceDocument(
        id="skills-source-1",
        source_type="linkedin",
        source_url="https://example.com/job/1",
        raw_text="Application Support Engineer\nSQL REST API PowerShell",
        content_hash="a" * 64,
        captured_at=now,
    )
    posting = Posting(
        id="skills-posting-1",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key="skills:1",
        title="Application Support Engineer",
        company="Example",
        location="Remote Europe",
        description=source.raw_text,
        identity_status="verified",
        created_at=now,
    )
    profile = LinkedInPresenceCapture(
        id="skills-profile-1",
        category="profile",
        title="Profile",
        source_url="https://www.linkedin.com/in/example/",
        visible_text="IT Operations | PowerShell | Microsoft 365",
        notes="Profile evidence.",
        content_hash="b" * 64,
        previous_capture_id=None,
        changed_since_previous=False,
        captured_at=now,
    )
    session.add(source)
    session.flush()
    session.add_all([posting, profile])
    session.commit()
    monkeypatch.setattr(
        "jolt.skills_preparation_exchange.build_global_context_snapshot",
        lambda: {"job_search_preferences": {}, "ai_context": {}, "ownership": {}},
    )

    try:
        exchange = build_skills_preparation_exchange(session)
    finally:
        session.close()

    assert exchange.scope.section == "skills_gaps"
    assert exchange.evidence["counts"] == {"vacancies": 1, "profile_captures": 1}
    assert "SQL REST API PowerShell" in exchange.evidence["vacancies"][0]["evidence_text"]
    assert "PowerShell" in exchange.evidence["profile_evidence"][0]["visible_text"]
    serialized = json.dumps(exchange.evidence).casefold()
    assert '"ranking_score"' not in serialized
    assert '"recommendation"' not in serialized
    assert '"learning_signals"' not in serialized
    assert '"gap_count"' not in serialized


def test_skills_exchange_import_updates_context_and_creates_preparation_actions(
    monkeypatch,
) -> None:
    saved_context: list[GlobalAIContextOverlay] = []
    saved_feedback: list[AIExchangeOutput] = []
    imported = []
    monkeypatch.setattr(
        "jolt.skills_preparation_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    monkeypatch.setattr(
        "jolt.skills_preparation_exchange.save_global_ai_context",
        lambda context: saved_context.append(context) or context,
    )
    monkeypatch.setattr(
        "jolt.skills_preparation_exchange.save_ai_exchange_feedback",
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
        actions = request.preparation_plan
        record = MarketPreparationImportRecord(
            id="prep-1",
            source=request.source,
            summary=request.summary,
            imported_at=datetime.now(UTC).isoformat(),
            action_count=len(actions),
            actions=actions,
            raw_payload=request.raw_payload,
        )
        return MarketPreparationImportResponse(imported_count=len(actions), latest_import=record)

    monkeypatch.setattr("jolt.skills_preparation_exchange.import_market_preparation", fake_import)
    output = AIExchangeOutput(
        exchange_id="skills-exchange-1",
        reviewed_at=datetime.now(UTC),
        review_version="skills-v1",
        scope=AIExchangeScope(
            section="skills_gaps",
            analysis_types=["gap_signal", "recommendation", "context_update"],
        ),
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="recommendation",
                entity_type="skill",
                entity_id="rest-api",
                payload={
                    "action_type": "practice",
                    "title": "Practice REST API troubleshooting",
                    "rationale": "Recurring requirement with partial represented evidence.",
                    "proposed_action": "Complete three ticket-style API failure scenarios.",
                    "priority": "high",
                },
                evidence_refs=["posting:1", "posting:2"],
            )
        ],
        context_patch={"skills_gap_summary": {"highest_leverage": ["REST API"]}},
        summary={"executive_summary": "Prioritize API troubleshooting evidence."},
    )

    response = import_skills_preparation_exchange(output)

    assert saved_context[0].skills_gap_summary["highest_leverage"] == ["REST API"]
    assert saved_feedback == [output]
    assert response.preparation.imported_count == 1
    assert imported[0].preparation_plan[0].action_type == "practice"
    assert "posting:1" in imported[0].preparation_plan[0].rationale


def test_skills_exchange_rejects_protected_patch(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.skills_preparation_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    output = AIExchangeOutput(
        exchange_id="skills-invalid",
        reviewed_at=datetime.now(UTC),
        review_version="skills-v1",
        scope=AIExchangeScope(section="skills_gaps", analysis_types=["context_update"]),
        context_patch={"job_search_preferences": {"languages": ["German"]}},
    )

    with pytest.raises(ValueError, match="non-patchable"):
        import_skills_preparation_exchange(output)
