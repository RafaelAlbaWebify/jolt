from datetime import UTC, datetime

from jolt.ai_exchange_contract import (
    AIExchangeFeedbackItem,
    AIExchangeOutput,
    AIExchangeScope,
    AIExchangeSection,
)
from jolt.ai_exchange_feedback_store import (
    list_ai_exchange_feedback,
    save_ai_exchange_feedback,
)


def _output(exchange_id: str, section: AIExchangeSection) -> AIExchangeOutput:
    return AIExchangeOutput(
        exchange_id=exchange_id,
        reviewed_at=datetime.now(UTC),
        review_version="feedback-v1",
        scope=AIExchangeScope(section=section, analysis_types=["recommendation"]),
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="recommendation",
                entity_type="strategy",
                entity_id=exchange_id,
                payload={"title": "Improve evidence"},
                confidence=90,
            )
        ],
        summary={"executive_summary": "Sample feedback"},
    )


def test_feedback_ledger_persists_and_filters(tmp_path, monkeypatch) -> None:
    path = tmp_path / "ai_exchange_feedback.json"
    monkeypatch.setattr("jolt.ai_exchange_feedback_store._data_path", lambda: path)

    first = save_ai_exchange_feedback(_output("exchange-1", "applications"))
    save_ai_exchange_feedback(_output("exchange-2", "market_insights"))

    assert first.section == "applications"
    index = list_ai_exchange_feedback(section="applications")
    assert index.total_import_count == 2
    assert len(index.records) == 1
    assert index.records[0].exchange_id == "exchange-1"
    assert index.records[0].feedback[0].payload["title"] == "Improve evidence"
