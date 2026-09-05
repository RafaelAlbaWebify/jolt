from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import cast
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import (
    AIExchangeFeedbackItem,
    AIExchangeOutput,
    AIExchangeScope,
)
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord
from jolt.database import LinkedInPresenceCapture, create_session_factory
from jolt.errors import JoltNotFoundError
from jolt.global_context import GlobalAIContextOverlay
from jolt.linkedin_command_center import LinkedInRecommendationImportResponse
from jolt.linkedin_profile_exchange import (
    build_linkedin_profile_exchange,
    import_linkedin_profile_exchange,
)


def test_linkedin_exchange_exports_capture_evidence_and_guardrails(tmp_path, monkeypatch) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    session.add(
        LinkedInPresenceCapture(
            id="linkedin-capture-1",
            category="profile",
            title="Profile snapshot",
            source_url="https://www.linkedin.com/in/example/",
            visible_text="Application Support | IT Operations\nSQL, Windows, M365",
            notes="User-approved capture.",
            content_hash="a" * 64,
            previous_capture_id=None,
            changed_since_previous=False,
            captured_at=now,
        )
    )
    session.commit()
    monkeypatch.setattr(
        "jolt.linkedin_profile_exchange.build_global_context_snapshot",
        lambda: {
            "job_search_preferences": {"languages": ["English", "Spanish"]},
            "ai_context": {},
            "ownership": {},
        },
    )

    try:
        exchange = build_linkedin_profile_exchange(session)
    finally:
        session.close()

    assert exchange.scope.section == "linkedin_profile"
    assert exchange.evidence["counts"]["captures"] == 1
    assert exchange.evidence["captures"][0]["title"] == "Profile snapshot"
    assert exchange.evidence["network_capture_quality"]["status"] == "not_captured"
    assert "Do not automate LinkedIn actions" in exchange.evidence["authority_notes"]["automation"]
    assert "linkedin_recommendation_statuses" in exchange.protected_state["non_patchable"]


def test_linkedin_exchange_exposes_partial_network_capture_quality(tmp_path, monkeypatch) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt-network.db').as_posix()}")()
    now = datetime.now(UTC)
    structured = {
        "schema": "jolt_linkedin_connections_v1",
        "capture_run": {
            "requested_limit": 100,
            "observed_count": 76,
            "unique_count": 19,
            "duplicate_count": 57,
            "scroll_count": 3,
            "stop_reason": "no_new_connections_after_scroll",
            "status": "partial",
            "failures": [],
        },
        "connections": [
            {
                "name": "Example Recruiter",
                "profile_url": "https://www.linkedin.com/in/example-recruiter/",
                "headline": "Technical Recruiter",
                "connection_context": "1st degree connection",
                "capture_order": 1,
            }
        ],
    }
    session.add(
        LinkedInPresenceCapture(
            id="connections-capture-1",
            category="network_contact",
            title="Connections",
            source_url="https://www.linkedin.com/mynetwork/invite-connect/connections/",
            visible_text=json.dumps(structured),
            notes="User-supervised network capture.",
            content_hash="b" * 64,
            previous_capture_id=None,
            changed_since_previous=False,
            captured_at=now,
        )
    )
    session.commit()
    monkeypatch.setattr(
        "jolt.linkedin_profile_exchange.build_global_context_snapshot",
        lambda: {
            "job_search_preferences": {"languages": ["English", "Spanish"]},
            "ai_context": {},
            "ownership": {},
        },
    )

    try:
        exchange = build_linkedin_profile_exchange(session)
    finally:
        session.close()

    quality = exchange.evidence["network_capture_quality"]
    assert quality["available"] is True
    assert quality["status"] == "partial"
    assert quality["requested_limit"] == 100
    assert quality["unique_count"] == 19
    assert quality["complete_for_requested_limit"] is False
    assert quality["bounded_sample"] is True
    assert "partial" in quality["coverage_warning"].lower()
    assert "never infer" in exchange.evidence["authority_notes"]["network_contacts"].lower()


def test_linkedin_exchange_import_updates_context_and_creates_pending_recommendation(
    monkeypatch,
) -> None:
    saved_context: list[GlobalAIContextOverlay] = []
    saved_feedback: list[AIExchangeOutput] = []
    imported_requests = []
    monkeypatch.setattr(
        "jolt.linkedin_profile_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    monkeypatch.setattr(
        "jolt.linkedin_profile_exchange.save_global_ai_context",
        lambda context: saved_context.append(context) or context,
    )
    monkeypatch.setattr(
        "jolt.linkedin_profile_exchange.save_ai_exchange_feedback",
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

    def fake_import(_session, request):
        imported_requests.append(request)
        return LinkedInRecommendationImportResponse(
            imported_count=len(request.recommendations),
            recommendations=[],
        )

    monkeypatch.setattr(
        "jolt.linkedin_profile_exchange.import_linkedin_recommendations", fake_import
    )

    output = AIExchangeOutput(
        exchange_id="linkedin-exchange-1",
        reviewed_at=datetime.now(UTC),
        review_version="linkedin-v1",
        scope=AIExchangeScope(
            section="linkedin_profile",
            analysis_types=["recommendation", "context_update", "audit_result"],
        ),
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="recommendation",
                entity_type="linkedin_profile",
                entity_id="headline",
                payload={
                    "recommendation_type": "profile_update",
                    "target_area": "headline",
                    "title": "Clarify target role",
                    "rationale": "Captured headline does not lead with Application Support.",
                    "proposed_action": "Edit the headline manually.",
                    "proposed_text": "Application Support Engineer | IT Operations",
                    "priority": "high",
                },
                confidence=90,
            )
        ],
        context_patch={"profile_strategy": {"headline_focus": "Application Support"}},
    )
    session_mock = MagicMock(spec=Session)
    session_mock.get.return_value = object()
    mock_session = cast(Session, session_mock)

    response = import_linkedin_profile_exchange(mock_session, output)

    assert saved_context[0].profile_strategy["headline_focus"] == "Application Support"
    assert saved_feedback == [output]
    assert response.recommendations.imported_count == 1
    recommendation = imported_requests[0].recommendations[0]
    assert recommendation.recommendation_type == "profile_update"
    assert recommendation.status == "pending"
    assert recommendation.priority == "high"


def test_linkedin_exchange_import_rejects_unknown_capture_before_side_effects(monkeypatch) -> None:
    saved_context: list[GlobalAIContextOverlay] = []
    saved_feedback: list[AIExchangeOutput] = []
    monkeypatch.setattr(
        "jolt.linkedin_profile_exchange.save_global_ai_context",
        lambda context: saved_context.append(context) or context,
    )
    monkeypatch.setattr(
        "jolt.linkedin_profile_exchange.save_ai_exchange_feedback",
        lambda output: saved_feedback.append(output),
    )
    output = AIExchangeOutput(
        exchange_id="linkedin-stale-capture",
        reviewed_at=datetime.now(UTC),
        review_version="linkedin-v1",
        scope=AIExchangeScope(section="linkedin_profile", analysis_types=["recommendation"]),
        feedback=[
            AIExchangeFeedbackItem(
                feedback_type="recommendation",
                entity_type="linkedin_profile",
                entity_id="headline",
                payload={
                    "capture_id": "missing-capture",
                    "recommendation_type": "profile_update",
                    "title": "Update headline",
                },
            )
        ],
    )
    session_mock = MagicMock(spec=Session)
    session_mock.get.return_value = None
    mock_session = cast(Session, session_mock)

    with pytest.raises(JoltNotFoundError, match="missing-capture"):
        import_linkedin_profile_exchange(mock_session, output)

    assert saved_context == []
    assert saved_feedback == []


def test_linkedin_exchange_import_rejects_protected_patch(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.linkedin_profile_exchange.load_global_ai_context",
        lambda: GlobalAIContextOverlay(),
    )
    output = AIExchangeOutput(
        exchange_id="linkedin-invalid",
        reviewed_at=datetime.now(UTC),
        review_version="linkedin-v1",
        scope=AIExchangeScope(section="linkedin_profile", analysis_types=["context_update"]),
        context_patch={"job_search_preferences": {"languages": ["German"]}},
    )
    mock_session = cast(Session, object())

    with pytest.raises(ValueError, match="non-patchable"):
        import_linkedin_profile_exchange(mock_session, output)
