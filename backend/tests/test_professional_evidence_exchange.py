from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jolt.ai_exchange_contract import AIExchangeFeedbackItem, AIExchangeOutput, AIExchangeScope
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord
from jolt.database import create_session_factory
from jolt.global_context import GlobalAIContextOverlay
from jolt.professional_evidence_exchange import (
    build_professional_evidence_exchange,
    import_professional_evidence_exchange,
)
from jolt.professional_intelligence_evidence_review import (
    ProfessionalEvidenceArtifactReview,
    ProfessionalEvidenceRunReview,
    ProfessionalEvidenceSourceReview,
)
from jolt.professional_intelligence_records import ProfessionalCaptureRun


def _completed_run(now: datetime) -> ProfessionalCaptureRun:
    return ProfessionalCaptureRun(
        id="professional-run-1",
        mode="supervised_read_only",
        status="completed",
        source_snapshot_json="[]",
        safety_constraints_json="[]",
        capture_options_json=(
            '{"max_sources":1,"max_scroll_batches":1,"max_items_per_source":10,'
            '"timeout_seconds":30,"stop_on_failure":true}'
        ),
        source_progress_json="[]",
        completed_source_count=1,
        current_source_id="",
        cancel_requested=False,
        progress_updated_at=now,
        requested_at=now,
        authorized_at=now,
        authorization_expires_at=now,
        user_present_confirmed=True,
        started_at=now,
        completed_at=now,
        stop_reason="completed",
    )


def test_professional_exchange_exports_only_integrity_verified_reviewable_evidence(
    tmp_path, monkeypatch
) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    session.add(_completed_run(now))
    session.commit()
    review = ProfessionalEvidenceRunReview(
        capture_run_id="professional-run-1",
        run_status="completed",
        integrity_valid=True,
        review_available=True,
        ready_for_analysis=True,
        sources=[
            ProfessionalEvidenceSourceReview(
                source_id="linkedin-experience",
                completeness_status="complete",
                artifacts=[
                    ProfessionalEvidenceArtifactReview(
                        id="artifact-good",
                        source_id="linkedin-experience",
                        artifact_type="rendered_text_json",
                        relative_path="professional-intelligence/professional-run-1/linkedin-experience/rendered.json",
                        completeness_status="complete",
                        retention_days=30,
                        exists=True,
                        integrity_valid=True,
                        reviewable=True,
                        content={"text": "IT Support Engineer experience with Windows and PowerShell."},
                    ),
                    ProfessionalEvidenceArtifactReview(
                        id="artifact-bad",
                        source_id="linkedin-experience",
                        artifact_type="rendered_text_json",
                        relative_path="professional-intelligence/professional-run-1/linkedin-experience/bad.json",
                        completeness_status="partial",
                        retention_days=30,
                        exists=True,
                        integrity_valid=False,
                        reviewable=True,
                        content={"text": "Untrusted content"},
                    ),
                ],
            )
        ],
    )
    monkeypatch.setattr(
        "jolt.professional_evidence_exchange.review_professional_capture_evidence",
        lambda _session, _run_id: review,
    )
    monkeypatch.setattr(
        "jolt.professional_evidence_exchange.build_global_context_snapshot",
        lambda: {"job_search_preferences": {}, "ai_context": {}, "ownership": {}},
    )

    try:
        exchange = build_professional_evidence_exchange(session)
    finally:
        session.close()

    assert exchange.scope.section == "professional_evidence"
    assert exchange.evidence["counts"] == {
        "capture_runs": 1,
        "verified_reviews": 1,
        "review_errors": 0,
    }
    artifacts = exchange.evidence["verified_reviews"][0]["sources"][0]["artifacts"]
    assert [item["artifact_id"] for item in artifacts] == ["artifact-good"]
    assert "Windows and PowerShell" in artifacts[0]["content"]["text"]
    assert "deterministic term extraction is intentionally excluded" in exchange.evidence[
        "authority_notes"
    ]["reasoning"].casefold()


def test_professional_exchange_import_updates_evidence_context_and_feedback(monkeypatch) -> None:
    saved_context: list[GlobalAIContextOverlay] = []
    saved_feedback: list[AIExchangeOutput] = []
    monkeypatch.setattr(
        "jolt.professional_evidence_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    monkeypatch.setattr(
        "jolt.professional_evidence_exchange.save_global_ai_context",
        lambda context: saved_context.append(context) or context,
    )
    monkeypatch.setattr(
        "jolt.professional_evidence_exchange.save_ai_exchange_feedback",
        lambda output: saved_feedback.append(output)
        or AIExchangeFeedbackRecord(
            id="feedback-1",
            exchange_id=output.exchange_id,
            section=output.scope.section,
            review_version=output.review_version,
            reviewed_at=output.reviewed_at,
            imported_at=datetime.now(UTC),
            feedback=output.feedback,
            summary=output.summary,
        ),
    )
    output = AIExchangeOutput(
        exchange_id="professional-exchange-1",
        reviewed_at=datetime.now(UTC),
        review_version="professional-v1",
        scope=AIExchangeScope(
            section="professional_evidence",
            analysis_types=["extraction", "audit_result", "context_update"],
        ),
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="audit_result",
                entity_type="professional_evidence",
                entity_id="powershell",
                payload={"finding": "PowerShell is explicitly represented in verified evidence."},
                confidence=95,
            )
        ],
        context_patch={
            "professional_evidence_summary": {
                "explicit_strengths": ["PowerShell", "Windows support"]
            },
            "profile_strategy": {"lead_with": "Application Support and IT Operations"},
        },
    )

    response = import_professional_evidence_exchange(output)

    assert saved_context[0].professional_evidence_summary["explicit_strengths"] == [
        "PowerShell",
        "Windows support",
    ]
    assert saved_context[0].profile_strategy["lead_with"] == "Application Support and IT Operations"
    assert saved_feedback == [output]
    assert response.feedback_record.exchange_id == "professional-exchange-1"


def test_professional_exchange_rejects_protected_patch(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.professional_evidence_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    output = AIExchangeOutput(
        exchange_id="professional-invalid",
        reviewed_at=datetime.now(UTC),
        review_version="professional-v1",
        scope=AIExchangeScope(section="professional_evidence", analysis_types=["context_update"]),
        context_patch={"job_search_preferences": {"languages": ["German"]}},
    )

    with pytest.raises(ValueError, match="non-patchable"):
        import_professional_evidence_exchange(output)
