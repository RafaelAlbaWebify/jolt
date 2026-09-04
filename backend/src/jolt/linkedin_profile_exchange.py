from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput, AIExchangeScope
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord, save_ai_exchange_feedback
from jolt.candidate_evidence import profile_capture_quality_issue
from jolt.database import LinkedInPresenceCapture
from jolt.errors import JoltNotFoundError
from jolt.global_context import (
    GlobalAIContextOverlay,
    build_global_context_snapshot,
    global_context_version,
    load_global_ai_context,
    save_global_ai_context,
)
from jolt.linkedin_command_center import (
    LinkedInRecommendationImportItem,
    LinkedInRecommendationImportRequest,
    LinkedInRecommendationImportResponse,
    import_linkedin_recommendations,
    list_linkedin_command_center,
)

_LINKEDIN_PATCH_KEYS = frozenset({"profile_strategy", "capture_strategy", "audit_summary"})
_LINKEDIN_RECOMMENDATION_TYPES = {
    "profile_update",
    "network_decision",
    "content_action",
    "outreach",
    "lead_research",
    "cleanup",
}
_PROFILE_CATEGORIES = frozenset({"profile", "public_profile"})
_CONNECTION_SCHEMA = "jolt_linkedin_connections_v1"


class LinkedInProfileExchangeImportResponse(BaseModel):
    context: GlobalAIContextOverlay
    feedback_record: AIExchangeFeedbackRecord
    recommendations: LinkedInRecommendationImportResponse


def _latest_network_capture_quality(captures: list[dict[str, Any]]) -> dict[str, Any]:
    network_captures = [
        capture for capture in captures if str(capture.get("category", "")) == "network_contact"
    ]
    if not network_captures:
        return {
            "available": False,
            "status": "not_captured",
            "bounded_sample": True,
            "complete_for_requested_limit": False,
            "coverage_warning": (
                "No structured Connections capture is available. Do not infer anything about the user's "
                "network from missing contact evidence."
            ),
        }

    latest = max(network_captures, key=lambda item: str(item.get("captured_at", "")))
    try:
        structured = json.loads(str(latest.get("visible_text", "")))
    except json.JSONDecodeError:
        structured = None

    if not isinstance(structured, dict) or structured.get("schema") != _CONNECTION_SCHEMA:
        return {
            "available": True,
            "capture_id": str(latest.get("id", "")),
            "captured_at": str(latest.get("captured_at", "")),
            "status": "unstructured",
            "bounded_sample": True,
            "complete_for_requested_limit": False,
            "coverage_warning": (
                "The latest network-contact capture is not structured Connections evidence. Treat network "
                "coverage as unknown and do not infer that uncaptured people are absent."
            ),
        }

    run = structured.get("capture_run")
    if not isinstance(run, dict):
        run = {}
    connections = structured.get("connections")
    if not isinstance(connections, list):
        connections = []

    status = str(run.get("status", "partial"))
    stop_reason = str(run.get("stop_reason", "unknown"))
    requested_limit = int(run.get("requested_limit", 0) or 0)
    unique_count = int(run.get("unique_count", len(connections)) or 0)
    complete_for_requested_limit = (
        status == "complete"
        and stop_reason == "requested_limit_reached"
        and requested_limit > 0
        and unique_count >= requested_limit
    )

    return {
        "available": True,
        "capture_id": str(latest.get("id", "")),
        "captured_at": str(latest.get("captured_at", "")),
        "status": status,
        "stop_reason": stop_reason,
        "requested_limit": requested_limit,
        "observed_count": int(run.get("observed_count", 0) or 0),
        "unique_count": unique_count,
        "duplicate_count": int(run.get("duplicate_count", 0) or 0),
        "scroll_count": int(run.get("scroll_count", 0) or 0),
        "scroll_strategies": run.get("scroll_strategies", []),
        "failures": run.get("failures", []),
        "bounded_sample": True,
        "complete_for_requested_limit": complete_for_requested_limit,
        "coverage_warning": (
            "This is a bounded Connections sample, not proof of the full LinkedIn network. Missing people "
            "must never be treated as absent."
            if complete_for_requested_limit
            else "The latest Connections capture is partial. Use captured contacts as positive evidence only; "
            "missing people must never be treated as absent."
        ),
    }


def _command_center_evidence(session: Session) -> dict[str, Any]:
    command_center = list_linkedin_command_center(session)
    payload = command_center.model_dump(mode="json")
    raw_captures = payload.get("captures", [])
    usable_captures: list[dict[str, Any]] = []
    excluded_captures: list[dict[str, Any]] = []

    if isinstance(raw_captures, list):
        for raw_capture in raw_captures:
            if not isinstance(raw_capture, dict):
                continue
            category = str(raw_capture.get("category", ""))
            if category not in _PROFILE_CATEGORIES:
                usable_captures.append(raw_capture)
                continue

            capture_id = str(raw_capture.get("id", ""))
            capture = session.get(LinkedInPresenceCapture, capture_id) if capture_id else None
            quality_issue = profile_capture_quality_issue(capture) if capture is not None else None
            if quality_issue is None:
                usable_captures.append(raw_capture)
                continue

            excluded_captures.append(
                {
                    "capture_id": capture_id,
                    "title": str(raw_capture.get("title", "")),
                    "category": category,
                    "captured_at": str(raw_capture.get("captured_at", "")),
                    "reason": quality_issue,
                }
            )

    return {
        "captures": usable_captures,
        "excluded_profile_captures": excluded_captures,
        "existing_recommendations": payload.get("recommendations", []),
        "counts": {
            "captures": command_center.capture_count,
            "recommendations": command_center.recommendation_count,
            "open_recommendations": command_center.open_recommendation_count,
        },
        "profile_capture_quality": {
            "usable_exported_captures": len(usable_captures),
            "invalid_profile_captures": len(excluded_captures),
        },
        "network_capture_quality": _latest_network_capture_quality(usable_captures),
        "categories": command_center.categories,
        "recommendation_statuses": command_center.recommendation_statuses,
        "recommendation_types": command_center.recommendation_types,
        "authority_notes": {
            "captures": (
                "User-supervised LinkedIn evidence only. LinkedIn login/authwall/checkpoint captures "
                "are excluded from AI evidence; missing profile data must not be treated as negative evidence."
            ),
            "excluded_profile_captures": (
                "Retained for audit only. These captures must not support profile, candidate-fit, or "
                "professional-evidence conclusions."
            ),
            "network_contacts": (
                "Connections capture is bounded and may be partial. Captured contacts are positive evidence only; "
                "never infer that an uncaptured person is not in the user's network."
            ),
            "recommendations": (
                "Existing recommendation status is JOLT/user-owned workflow state and must not be overwritten."
            ),
            "automation": "Do not automate LinkedIn actions, messaging, connections, follows, or profile edits.",
        },
    }


def build_linkedin_profile_exchange(session: Session) -> AIExchangeInput:
    context = build_global_context_snapshot()
    return AIExchangeInput(
        generated_at=datetime.now(UTC),
        exchange_id=str(uuid4()),
        context_version=global_context_version(context),
        scope=AIExchangeScope(
            section="linkedin_profile",
            analysis_types=["recommendation", "context_update", "audit_result", "extraction"],
            scope_label="JOLT LinkedIn profile, activity, and network evidence",
        ),
        context=context,
        evidence=_command_center_evidence(session),
        protected_state={
            "patchable_context_namespaces": sorted(_LINKEDIN_PATCH_KEYS),
            "non_patchable": [
                "linkedin_captures",
                "linkedin_recommendation_statuses",
                "job_search_preferences",
                "human_review_decisions",
                "applications",
            ],
        },
        requested_output={
            "feedback": {
                "audit_result": "Evidence-backed profile, activity, network, or capture-quality findings.",
                "recommendation": (
                    "Manual LinkedIn action. For importable recommendations include recommendation_type, "
                    "target_area, title, rationale, proposed_action, optional proposed_text, and priority."
                ),
            },
            "context_patch": (
                "Return only changed profile_strategy, capture_strategy, or audit_summary namespaces."
            ),
            "summary": "Include executive_summary, high_confidence_findings, and evidence_gaps.",
        },
    )


def _apply_linkedin_context_patch(output: AIExchangeOutput) -> GlobalAIContextOverlay:
    unknown = sorted(set(output.context_patch) - _LINKEDIN_PATCH_KEYS)
    if unknown:
        raise ValueError(
            f"LinkedIn context patch contains non-patchable keys: {', '.join(unknown)}"
        )

    current = load_global_ai_context()
    update = current.model_dump()
    for key, value in output.context_patch.items():
        if not isinstance(value, dict):
            raise ValueError(f"LinkedIn context namespace '{key}' must be an object")
        update[key] = value
    update["updated_at"] = output.reviewed_at
    update["updated_by"] = f"chatgpt:{output.review_version}"
    return save_global_ai_context(GlobalAIContextOverlay.model_validate(update))


def _recommendation_items(output: AIExchangeOutput) -> list[LinkedInRecommendationImportItem]:
    items: list[LinkedInRecommendationImportItem] = []
    for feedback in output.feedback:
        if feedback.feedback_type != "recommendation":
            continue
        payload = feedback.payload
        raw_type = payload.get("recommendation_type")
        if raw_type not in _LINKEDIN_RECOMMENDATION_TYPES:
            continue
        raw_priority = payload.get("priority", "medium")
        if raw_priority not in {"high", "medium", "low"}:
            raw_priority = "medium"
        recommendation_type = cast(
            Literal[
                "profile_update",
                "network_decision",
                "content_action",
                "outreach",
                "lead_research",
                "cleanup",
            ],
            raw_type,
        )
        priority = cast(Literal["high", "medium", "low"], raw_priority)
        capture_id = payload.get("capture_id")
        if capture_id is not None and not isinstance(capture_id, str):
            capture_id = None
        items.append(
            LinkedInRecommendationImportItem(
                capture_id=capture_id,
                recommendation_type=recommendation_type,
                target_area=str(payload.get("target_area", "")),
                title=str(payload.get("title", ""))[:240] or "Review LinkedIn evidence",
                rationale=str(payload.get("rationale", "")),
                proposed_action=str(payload.get("proposed_action", "")),
                proposed_text=str(payload.get("proposed_text", "")),
                priority=priority,
                status="pending",
            )
        )
    return items


def _validate_capture_references(
    session: Session,
    recommendations: list[LinkedInRecommendationImportItem],
) -> None:
    for recommendation in recommendations:
        capture_id = recommendation.capture_id
        if capture_id and session.get(LinkedInPresenceCapture, capture_id) is None:
            raise JoltNotFoundError(f"LinkedIn capture {capture_id} was not found")


def import_linkedin_profile_exchange(
    session: Session,
    output: AIExchangeOutput,
) -> LinkedInProfileExchangeImportResponse:
    if output.scope.section != "linkedin_profile":
        raise ValueError("LinkedIn profile import requires scope.section=linkedin_profile")

    recommendation_items = _recommendation_items(output)
    _validate_capture_references(session, recommendation_items)
    context = _apply_linkedin_context_patch(output)
    feedback_record = save_ai_exchange_feedback(output)
    recommendations = import_linkedin_recommendations(
        session,
        LinkedInRecommendationImportRequest(
            source="chatgpt_linkedin_profile_exchange",
            recommendations=recommendation_items,
        ),
    )
    return LinkedInProfileExchangeImportResponse(
        context=context,
        feedback_record=feedback_record,
        recommendations=recommendations,
    )
