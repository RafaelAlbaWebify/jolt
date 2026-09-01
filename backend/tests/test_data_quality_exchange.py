from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from jolt.ai_exchange_contract import (
    AIExchangeFeedbackItem,
    AIExchangeOutput,
    AIExchangeScope,
)
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord
from jolt.data_quality_exchange import build_data_quality_exchange, import_data_quality_exchange
from jolt.database import CaptureItem, CaptureRun, Posting, SourceDocument, create_session_factory
from jolt.global_context import GlobalAIContextOverlay
from jolt.market_preparation_import import (
    MarketPreparationImportRecord,
    MarketPreparationImportResponse,
)


def test_data_quality_exchange_exports_deterministic_facts_and_source_evidence(
    tmp_path, monkeypatch
) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    raw_text = "Application Support Engineer\nRemote Europe\nSQL troubleshooting"
    source = SourceDocument(
        id="dq-source-1",
        source_type="linkedin",
        source_url="https://example.com/jobs/1",
        raw_text=raw_text,
        content_hash=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        captured_at=now,
    )
    posting = Posting(
        id="dq-posting-1",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key="dq:1",
        title="Application Support Engineer",
        company="Example",
        location="Remote Europe",
        description=raw_text,
        identity_status="verified",
        created_at=now,
    )
    run = CaptureRun(
        id="dq-run-1",
        source="linkedin",
        mode="supervised_live",
        status="completed",
        search_url="https://example.com/search",
        warnings_json="[]",
        requested_item_limit=10,
        observed_item_count=1,
        stop_reason="requested_limit_reached",
        started_at=now,
        completed_at=now,
    )
    item = CaptureItem(
        id="dq-item-1",
        capture_run_id=run.id,
        source_job_id="1",
        source_url=source.source_url,
        title=posting.title,
        company=posting.company,
        location=posting.location,
        detail_status="verified",
        verification_reasons_json="[]",
        source_document_id=source.id,
        posting_id=posting.id,
    )
    session.add_all([source, run])
    session.flush()
    session.add(posting)
    session.flush()
    session.add(item)
    session.commit()
    monkeypatch.setattr(
        "jolt.data_quality_exchange.build_global_context_snapshot",
        lambda: {"job_search_preferences": {}, "ai_context": {}, "ownership": {}},
    )

    try:
        exchange = build_data_quality_exchange(session)
    finally:
        session.close()

    assert exchange.scope.section == "data_quality"
    assert exchange.evidence["counts"]["deterministic_findings"] == 0
    posting_row = exchange.evidence["postings"][0]
    assert posting_row["source_hash_valid"] is True
    assert posting_row["posting_description_matches_source"] is True
    assert "SQL troubleshooting" in posting_row["source_evidence_text"]
    assert exchange.evidence["capture_runs"][0]["items"][0]["linkage_structurally_valid"] is True


def test_data_quality_exchange_surfaces_structural_mismatch_without_semantic_decision(
    tmp_path, monkeypatch
) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    run = CaptureRun(
        id="dq-run-bad",
        source="linkedin",
        mode="supervised_live",
        status="completed",
        search_url="https://example.com/search",
        warnings_json="[]",
        requested_item_limit=10,
        observed_item_count=2,
        stop_reason="requested_limit_reached",
        started_at=now,
        completed_at=now,
    )
    session.add(run)
    session.commit()
    monkeypatch.setattr(
        "jolt.data_quality_exchange.build_global_context_snapshot",
        lambda: {"job_search_preferences": {}, "ai_context": {}, "ownership": {}},
    )

    try:
        exchange = build_data_quality_exchange(session)
    finally:
        session.close()

    findings = exchange.evidence["deterministic_findings"]
    assert findings[0]["finding_type"] == "capture_count_mismatch"
    assert "does not decide whether" in exchange.evidence["authority_notes"]["semantic_authority"]


def test_data_quality_import_updates_audit_context_and_creates_pending_follow_up(
    monkeypatch,
) -> None:
    saved_context: list[GlobalAIContextOverlay] = []
    saved_feedback: list[AIExchangeOutput] = []
    imported = []
    monkeypatch.setattr(
        "jolt.data_quality_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    monkeypatch.setattr(
        "jolt.data_quality_exchange.save_global_ai_context",
        lambda context: saved_context.append(context) or context,
    )
    monkeypatch.setattr(
        "jolt.data_quality_exchange.save_ai_exchange_feedback",
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
        actions = request.market_recommendations
        record = MarketPreparationImportRecord(
            id="dq-action-1",
            source=request.source,
            summary=request.summary,
            imported_at=datetime.now(UTC).isoformat(),
            action_count=len(actions),
            actions=actions,
            raw_payload=request.raw_payload,
        )
        return MarketPreparationImportResponse(imported_count=len(actions), latest_import=record)

    monkeypatch.setattr("jolt.data_quality_exchange.import_market_preparation", fake_import)
    output = AIExchangeOutput(
        exchange_id="dq-exchange-1",
        reviewed_at=datetime.now(UTC),
        review_version="dq-v1",
        scope=AIExchangeScope(
            section="data_quality",
            analysis_types=["audit_result", "recommendation", "context_update"],
        ),
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="recommendation",
                entity_type="capture_run",
                entity_id="dq-run-1",
                payload={
                    "action_type": "recapture",
                    "title": "Recapture stale source",
                    "rationale": "Evidence indicates source drift.",
                    "proposed_action": "Run a supervised recapture and compare again.",
                    "priority": "medium",
                },
                evidence_refs=["capture:dq-run-1"],
            )
        ],
        context_patch={"audit_summary": {"material_issue_count": 1}},
        summary={"executive_summary": "One evidence refresh is warranted."},
    )

    response = import_data_quality_exchange(output)

    assert saved_context[0].audit_summary["material_issue_count"] == 1
    assert saved_feedback == [output]
    assert response.actions.imported_count == 1
    assert imported[0].market_recommendations[0].status == "pending"
    assert imported[0].market_recommendations[0].action_type == "recapture"


def test_data_quality_import_rejects_protected_patch(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.data_quality_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    output = AIExchangeOutput(
        exchange_id="dq-invalid",
        reviewed_at=datetime.now(UTC),
        review_version="dq-v1",
        scope=AIExchangeScope(section="data_quality", analysis_types=["context_update"]),
        context_patch={"job_search_preferences": {"languages": ["German"]}},
    )

    with pytest.raises(ValueError, match="non-patchable"):
        import_data_quality_exchange(output)
