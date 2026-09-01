from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput, AIExchangeScope
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord, save_ai_exchange_feedback
from jolt.database import Application, ApplicationEvent, Outcome, Posting, ReviewDecision
from jolt.global_context import (
    GlobalAIContextOverlay,
    build_global_context_snapshot,
    global_context_version,
    load_global_ai_context,
    save_global_ai_context,
)
from jolt.preference_aware_evaluation import sanitize_capture_text

_APPLICATION_PATCH_KEYS = frozenset(
    {
        "application_strategy",
        "outcome_strategy",
        "audit_summary",
    }
)


class ApplicationOutcomesExchangeImportResponse(BaseModel):
    context: GlobalAIContextOverlay
    feedback_record: AIExchangeFeedbackRecord


def _application_evidence(session: Session) -> list[dict[str, Any]]:
    applications = session.scalars(
        select(Application).order_by(Application.created_at.desc(), Application.id)
    ).all()
    evidence: list[dict[str, Any]] = []
    for application in applications:
        posting = session.get(Posting, application.posting_id)
        events = session.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application.id)
            .order_by(ApplicationEvent.occurred_at, ApplicationEvent.id)
        ).all()
        outcome = session.scalar(select(Outcome).where(Outcome.application_id == application.id))
        review = session.scalar(
            select(ReviewDecision)
            .where(ReviewDecision.posting_id == application.posting_id)
            .order_by(ReviewDecision.reviewed_at.desc(), ReviewDecision.id.desc())
        )
        posting_text = sanitize_capture_text(posting.description) if posting is not None else ""
        evidence.append(
            {
                "application_id": application.id,
                "posting_id": application.posting_id,
                "status": application.status,
                "application_url": application.application_url,
                "resume_used": application.resume_used,
                "notes": application.notes,
                "created_at": application.created_at.isoformat(),
                "updated_at": application.updated_at.isoformat(),
                "human_review_decision": review.decision if review is not None else None,
                "posting": {
                    "title": posting.title if posting is not None else "",
                    "company": posting.company if posting is not None else "",
                    "location": posting.location if posting is not None else "",
                    "canonical_url": posting.canonical_url if posting is not None else "",
                    "evidence_text": posting_text,
                    "evidence_sha256": hashlib.sha256(posting_text.encode("utf-8")).hexdigest(),
                },
                "events": [
                    {
                        "event_type": event.event_type,
                        "from_status": event.from_status,
                        "to_status": event.to_status,
                        "notes": event.notes,
                        "occurred_at": event.occurred_at.isoformat(),
                    }
                    for event in events
                ],
                "outcome": (
                    {
                        "outcome_type": outcome.outcome_type,
                        "stage_reached": outcome.stage_reached,
                        "reason_code": outcome.reason_code,
                        "notes": outcome.notes,
                        "recorded_at": outcome.recorded_at.isoformat(),
                    }
                    if outcome is not None
                    else None
                ),
            }
        )
    return evidence


def build_application_outcomes_exchange(session: Session) -> AIExchangeInput:
    context = build_global_context_snapshot()
    applications = _application_evidence(session)
    completed = sum(item["outcome"] is not None for item in applications)
    return AIExchangeInput(
        generated_at=datetime.now(UTC),
        exchange_id=str(uuid4()),
        context_version=global_context_version(context),
        scope=AIExchangeScope(
            section="applications",
            analysis_types=["recommendation", "context_update", "audit_result"],
            scope_label="JOLT application lifecycle and outcomes",
        ),
        context=context,
        evidence={
            "applications": applications,
            "counts": {
                "applications": len(applications),
                "with_outcomes": completed,
                "active_or_open": len(applications) - completed,
            },
            "authority_notes": {
                "application_state": "Recorded JOLT workflow state is evidence and must not be rewritten by AI.",
                "human_review_decision": "Human pursue/reject state is user-owned evidence, never patchable.",
                "local_fit_scores": "JOLT local recommendation and ranking fields are intentionally excluded.",
            },
        },
        protected_state={
            "patchable_context_namespaces": sorted(_APPLICATION_PATCH_KEYS),
            "non_patchable": [
                "applications",
                "application_events",
                "outcomes",
                "human_review_decisions",
                "job_search_preferences",
            ],
        },
        requested_output={
            "feedback": {
                "audit_result": "Identify evidence-backed conversion, process, positioning, or outcome patterns.",
                "recommendation": "Suggest concrete application-process or positioning changes; do not mutate workflow state.",
            },
            "context_patch": (
                "Return only changed application_strategy, outcome_strategy, or audit_summary namespaces."
            ),
            "summary": "Include executive_summary, high_confidence_patterns, and insufficient_evidence notes.",
        },
    )


def _apply_application_context_patch(output: AIExchangeOutput) -> GlobalAIContextOverlay:
    unknown = sorted(set(output.context_patch) - _APPLICATION_PATCH_KEYS)
    if unknown:
        raise ValueError(
            f"Applications context patch contains non-patchable keys: {', '.join(unknown)}"
        )

    current = load_global_ai_context()
    update = current.model_dump()
    for key, value in output.context_patch.items():
        if not isinstance(value, dict):
            raise ValueError(f"Applications context namespace '{key}' must be an object")
        update[key] = value
    update["updated_at"] = output.reviewed_at
    update["updated_by"] = f"chatgpt:{output.review_version}"
    return save_global_ai_context(GlobalAIContextOverlay.model_validate(update))


def import_application_outcomes_exchange(
    output: AIExchangeOutput,
) -> ApplicationOutcomesExchangeImportResponse:
    if output.scope.section != "applications":
        raise ValueError("Applications import requires scope.section=applications")
    context = _apply_application_context_patch(output)
    feedback_record = save_ai_exchange_feedback(output)
    return ApplicationOutcomesExchangeImportResponse(
        context=context,
        feedback_record=feedback_record,
    )
