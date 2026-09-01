from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput, AIExchangeScope
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord, save_ai_exchange_feedback
from jolt.database import CaptureRun, Posting
from jolt.global_context import (
    GlobalAIContextOverlay,
    build_global_context_snapshot,
    global_context_version,
    load_global_ai_context,
    save_global_ai_context,
)
from jolt.job_search_preferences import load_job_search_preferences
from jolt.market_preparation_import import (
    MarketPreparationAction,
    MarketPreparationImportRequest,
    MarketPreparationImportResponse,
    import_market_preparation,
)
from jolt.preference_aware_evaluation import sanitize_capture_text

_SEARCH_PATCH_KEYS = frozenset({"capture_strategy", "audit_summary"})
_SEARCH_ACTION_TYPES = {
    "target_title",
    "keyword",
    "geography",
    "work_mode",
    "salary_targeting",
    "seniority",
    "source_coverage",
    "false_positive_reduction",
    "search_query",
}
_MAX_POSTINGS = 250
_MAX_CAPTURES = 50


class SearchPreferenceExchangeImportResponse(BaseModel):
    context: GlobalAIContextOverlay
    feedback_record: AIExchangeFeedbackRecord
    preparation: MarketPreparationImportResponse


def _posting_evidence(session: Session) -> list[dict[str, Any]]:
    postings = session.scalars(
        select(Posting).order_by(Posting.created_at.desc(), Posting.id).limit(_MAX_POSTINGS)
    ).all()
    rows: list[dict[str, Any]] = []
    for posting in postings:
        text = sanitize_capture_text(posting.description)
        rows.append(
            {
                "posting_id": posting.id,
                "title": posting.title,
                "company": posting.company,
                "location": posting.location,
                "canonical_url": posting.canonical_url,
                "identity_status": posting.identity_status,
                "created_at": posting.created_at.isoformat(),
                "evidence_text": text,
                "evidence_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    return rows


def _capture_evidence(session: Session) -> list[dict[str, Any]]:
    captures = session.scalars(
        select(CaptureRun).order_by(CaptureRun.started_at.desc(), CaptureRun.id).limit(_MAX_CAPTURES)
    ).all()
    return [
        {
            "capture_run_id": capture.id,
            "source": capture.source,
            "mode": capture.mode,
            "status": capture.status,
            "search_url": capture.search_url,
            "requested_item_limit": capture.requested_item_limit,
            "observed_item_count": capture.observed_item_count,
            "stop_reason": capture.stop_reason,
            "started_at": capture.started_at.isoformat(),
            "completed_at": capture.completed_at.isoformat() if capture.completed_at else None,
        }
        for capture in captures
    ]


def build_search_preference_exchange(session: Session) -> AIExchangeInput:
    context = build_global_context_snapshot()
    preferences = load_job_search_preferences()
    postings = _posting_evidence(session)
    captures = _capture_evidence(session)
    return AIExchangeInput(
        generated_at=datetime.now(UTC),
        exchange_id=str(uuid4()),
        context_version=global_context_version(context),
        scope=AIExchangeScope(
            section="search_preferences",
            analysis_types=["market_signal", "recommendation", "context_update", "audit_result"],
            scope_label="JOLT search strategy and user-owned preference evidence",
        ),
        context=context,
        evidence={
            "current_preferences": preferences.model_dump(mode="json"),
            "postings": postings,
            "capture_runs": captures,
            "counts": {"postings": len(postings), "capture_runs": len(captures)},
            "authority_notes": {
                "preferences": (
                    "current_preferences are explicit JOLT/user-owned settings. ChatGPT may recommend changes but must not rewrite them."
                ),
                "vacancies": "Vacancy body evidence outranks title, card, location label, or search-filter metadata when they conflict.",
                "local_rules": (
                    "JOLT local preference-aware regex/ranking conclusions are intentionally not exported as reasoning authority."
                ),
            },
        },
        protected_state={
            "patchable_context_namespaces": sorted(_SEARCH_PATCH_KEYS),
            "non_patchable": [
                "job_search_preferences",
                "human_review_decisions",
                "applications",
                "outcomes",
            ],
        },
        requested_output={
            "feedback": {
                "market_signal": (
                    "Identify evidence-backed search yield, false-positive, role-title, geography, seniority, salary, and source-coverage signals."
                ),
                "recommendation": (
                    "For importable search proposals include action_type, title, rationale, proposed_action, priority, and evidence_refs. "
                    "action_type must be one of target_title, keyword, geography, work_mode, salary_targeting, seniority, "
                    "source_coverage, false_positive_reduction, or search_query."
                ),
                "audit_result": "Flag preference/search assumptions that are unsupported, stale, internally inconsistent, or causing poor capture yield.",
            },
            "context_patch": "Return only changed capture_strategy or audit_summary namespaces.",
            "summary": "Include executive_summary, keep_preferences, proposed_changes, and evidence_gaps.",
        },
    )


def _apply_search_context_patch(output: AIExchangeOutput) -> GlobalAIContextOverlay:
    unknown = sorted(set(output.context_patch) - _SEARCH_PATCH_KEYS)
    if unknown:
        raise ValueError(
            f"Search preference context patch contains non-patchable keys: {', '.join(unknown)}"
        )
    current = load_global_ai_context()
    update = current.model_dump()
    for key, value in output.context_patch.items():
        if not isinstance(value, dict):
            raise ValueError(f"Search preference context namespace '{key}' must be an object")
        update[key] = value
    update["updated_at"] = output.reviewed_at
    update["updated_by"] = f"chatgpt:{output.review_version}"
    return save_global_ai_context(GlobalAIContextOverlay.model_validate(update))


def _search_actions(output: AIExchangeOutput) -> list[MarketPreparationAction]:
    actions: list[MarketPreparationAction] = []
    for feedback in output.feedback:
        if feedback.feedback_type != "recommendation":
            continue
        payload = feedback.payload
        raw_type = payload.get("action_type")
        if raw_type not in _SEARCH_ACTION_TYPES:
            continue
        raw_priority = payload.get("priority", "medium")
        if raw_priority not in {"high", "medium", "low"}:
            raw_priority = "medium"
        priority = cast(Literal["high", "medium", "low"], raw_priority)
        rationale = str(payload.get("rationale", ""))
        if feedback.evidence_refs:
            rationale = f"{rationale}\nEvidence: {', '.join(feedback.evidence_refs)}".strip()
        actions.append(
            MarketPreparationAction(
                action_type=str(raw_type),
                title=str(payload.get("title", ""))[:240] or "Review search strategy",
                rationale=rationale,
                proposed_action=str(payload.get("proposed_action", "")),
                priority=priority,
                status="pending",
                source="chatgpt_search_preference_exchange",
            )
        )
    return actions


def import_search_preference_exchange(
    output: AIExchangeOutput,
) -> SearchPreferenceExchangeImportResponse:
    if output.scope.section != "search_preferences":
        raise ValueError("Search preference import requires scope.section=search_preferences")

    context = _apply_search_context_patch(output)
    feedback_record = save_ai_exchange_feedback(output)
    executive_summary = output.summary.get("executive_summary", "")
    if not isinstance(executive_summary, str):
        executive_summary = json.dumps(executive_summary, ensure_ascii=False, sort_keys=True)
    preparation = import_market_preparation(
        MarketPreparationImportRequest(
            source="chatgpt_search_preference_exchange",
            summary=executive_summary,
            search_filter_improvements=_search_actions(output),
            raw_payload=output.model_dump(mode="json"),
        )
    )
    return SearchPreferenceExchangeImportResponse(
        context=context,
        feedback_record=feedback_record,
        preparation=preparation,
    )
