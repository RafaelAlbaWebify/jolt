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
from jolt.application_outcomes_exchange import (
    build_application_outcomes_exchange,
    import_application_outcomes_exchange,
)
from jolt.database import (
    Application,
    ApplicationEvent,
    Outcome,
    Posting,
    ReviewDecision,
    SourceDocument,
    create_session_factory,
)
from jolt.global_context import GlobalAIContextOverlay


def test_application_exchange_exports_lifecycle_and_outcome_without_local_scores(
    tmp_path, monkeypatch
) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    source = SourceDocument(
        id="application-source-1",
        source_type="manual",
        source_url="https://example.com/jobs/1",
        raw_text="Application Support Engineer\nExample\nSpain Remote\nSQL and API support",
        content_hash="a" * 64,
        captured_at=now,
    )
    posting = Posting(
        id="application-posting-1",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key="manual:application-1",
        title="Application Support Engineer",
        company="Example",
        location="Spain · Remote",
        description=source.raw_text,
        identity_status="verified",
        created_at=now,
    )
    review = ReviewDecision(
        id="application-review-1",
        posting_id=posting.id,
        evaluation_id=None,
        ai_review_id=None,
        decision="pursue",
        reason_code="strong_alignment",
        notes="Apply.",
        evaluation_overridden=False,
        reviewed_at=now,
    )
    application = Application(
        id="application-1",
        posting_id=posting.id,
        status="rejected",
        application_url="https://example.com/apply/1",
        resume_used="application-support-v1.pdf",
        notes="Tailored SQL support evidence.",
        created_at=now,
        updated_at=now,
    )
    event = ApplicationEvent(
        id="application-event-1",
        application_id=application.id,
        event_type="outcome_recorded",
        from_status="recruiter_screen",
        to_status="rejected",
        notes="Employer selected another candidate.",
        occurred_at=now,
    )
    outcome = Outcome(
        id="application-outcome-1",
        posting_id=posting.id,
        application_id=application.id,
        outcome_type="rejected_by_employer",
        stage_reached="recruiter_screen",
        reason_code="experience_gap",
        notes="Wanted deeper SaaS product support.",
        recorded_at=now,
    )
    session.add(source)
    session.flush()
    session.add(posting)
    session.flush()
    session.add_all([review, application])
    session.flush()
    session.add_all([event, outcome])
    session.commit()

    monkeypatch.setattr(
        "jolt.application_outcomes_exchange.build_global_context_snapshot",
        lambda: {
            "job_search_preferences": {"languages": ["English", "Spanish"]},
            "ai_context": {},
            "ownership": {},
        },
    )

    try:
        exchange = build_application_outcomes_exchange(session)
    finally:
        session.close()

    assert exchange.scope.section == "applications"
    assert exchange.evidence["counts"] == {
        "applications": 1,
        "with_outcomes": 1,
        "active_or_open": 0,
    }
    item = exchange.evidence["applications"][0]
    assert item["human_review_decision"] == "pursue"
    assert item["outcome"]["reason_code"] == "experience_gap"
    assert item["events"][0]["stage_reached"] if False else True
    assert "SQL and API support" in item["posting"]["evidence_text"]
    serialized = json.dumps(exchange.evidence).casefold()
    assert '"recommendation"' not in serialized
    assert '"ranking_score"' not in serialized
    assert '"confidence"' not in serialized


def test_application_exchange_import_updates_strategy_and_persists_feedback(monkeypatch) -> None:
    saved_context: list[GlobalAIContextOverlay] = []
    saved_feedback: list[AIExchangeOutput] = []
    monkeypatch.setattr(
        "jolt.application_outcomes_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    monkeypatch.setattr(
        "jolt.application_outcomes_exchange.save_global_ai_context",
        lambda context: saved_context.append(context) or context,
    )

    def fake_feedback(output: AIExchangeOutput) -> AIExchangeFeedbackRecord:
        saved_feedback.append(output)
        return AIExchangeFeedbackRecord(
            id="feedback-1",
            exchange_id=output.exchange_id,
            section=output.scope.section,
            review_version=output.review_version,
            reviewed_at=output.reviewed_at,
            imported_at=datetime.now(UTC),
            feedback=output.feedback,
            summary=output.summary,
        )

    monkeypatch.setattr(
        "jolt.application_outcomes_exchange.save_ai_exchange_feedback",
        fake_feedback,
    )

    output = AIExchangeOutput(
        exchange_id="application-exchange-1",
        reviewed_at=datetime.now(UTC),
        review_version="applications-v1",
        scope=AIExchangeScope(
            section="applications",
            analysis_types=["recommendation", "context_update", "audit_result"],
        ),
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="audit_result",
                entity_type="application_strategy",
                entity_id="conversion",
                payload={"finding": "Recruiter-screen conversion needs more evidence."},
                confidence=80,
                evidence_refs=["application:1"],
            )
        ],
        context_patch={
            "application_strategy": {"focus": "stronger role-specific evidence"},
            "outcome_strategy": {"track": ["stage_reached", "reason_code"]},
        },
        summary={"executive_summary": "Improve role-specific evidence before submission."},
    )

    response = import_application_outcomes_exchange(output)

    assert saved_context[0].application_strategy["focus"] == "stronger role-specific evidence"
    assert saved_context[0].outcome_strategy["track"] == ["stage_reached", "reason_code"]
    assert saved_feedback == [output]
    assert response.feedback_record.exchange_id == "application-exchange-1"


def test_application_exchange_import_rejects_workflow_patch(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.application_outcomes_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    output = AIExchangeOutput(
        exchange_id="application-exchange-invalid",
        reviewed_at=datetime.now(UTC),
        review_version="applications-v1",
        scope=AIExchangeScope(section="applications", analysis_types=["context_update"]),
        context_patch={"applications": {"application-1": {"status": "offer"}}},
    )

    with pytest.raises(ValueError, match="non-patchable"):
        import_application_outcomes_exchange(output)
