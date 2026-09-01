from datetime import UTC, datetime

from pydantic import ValidationError

from jolt.ai_exchange_contract import (
    AIExchangeFeedbackItem,
    AIExchangeInput,
    AIExchangeOutput,
    AIExchangeScope,
)


def test_universal_ai_exchange_input_supports_review_inbox() -> None:
    scope = AIExchangeScope(
        section="review_inbox",
        analysis_types=["classification", "duplicate_link", "priority_update"],
        scope_id="capture-123",
        scope_label="Latest LinkedIn capture",
    )
    document = AIExchangeInput(
        generated_at=datetime.now(UTC),
        exchange_id="exchange-123",
        context_version="context-7",
        scope=scope,
        context={"job_search_preferences": {"languages": ["English", "Spanish"]}},
        evidence={"jobs": [{"posting_id": "posting-1"}]},
        protected_state={"human_review_posting_ids": ["posting-9"]},
        requested_output={"return": "structured feedback only"},
    )

    assert document.contract_type == "jolt_ai_exchange_input"
    assert document.contract_version == "1.0"
    assert document.scope.section == "review_inbox"
    assert document.evidence["jobs"][0]["posting_id"] == "posting-1"


def test_universal_ai_exchange_output_carries_feedback_and_context_patch() -> None:
    scope = AIExchangeScope(
        section="market_insights",
        analysis_types=["market_signal", "gap_signal", "context_update"],
    )
    output = AIExchangeOutput(
        exchange_id="exchange-456",
        reviewed_at=datetime.now(UTC),
        review_version="chatgpt-jolt-2026-09-01",
        scope=scope,
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="market_signal",
                entity_type="skill",
                entity_id="powershell",
                payload={"frequency": 32, "direction": "stable"},
                confidence=92,
                evidence_refs=["job-1", "job-8"],
            )
        ],
        context_patch={"market_summary": {"powershell": "high-value recurring skill"}},
    )

    assert output.contract_type == "jolt_ai_exchange_output"
    assert output.feedback[0].feedback_type == "market_signal"
    assert output.context_patch["market_summary"]["powershell"]


def test_exchange_scope_rejects_unknown_section() -> None:
    try:
        AIExchangeScope(section="unknown", analysis_types=["audit_result"])
    except ValidationError:
        return
    raise AssertionError("Unknown JOLT section must fail validation")


def test_feedback_confidence_is_bounded() -> None:
    try:
        AIExchangeFeedbackItem(
            feedback_type="classification",
            entity_type="posting",
            entity_id="posting-1",
            confidence=101,
        )
    except ValidationError:
        return
    raise AssertionError("Confidence above 100 must fail validation")
