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
from jolt.database import CaptureRun, Posting
from jolt.global_context import (
    GlobalAIContextOverlay,
    build_global_context_snapshot,
    global_context_version,
    load_global_ai_context,
    save_global_ai_context,
)
from jolt.market_preparation_import import (
    MarketPreparationAction,
    MarketPreparationImportRequest,
    MarketPreparationImportResponse,
    import_market_preparation,
)
from jolt.preference_aware_evaluation import sanitize_capture_text

_MARKET_PATCH_KEYS = frozenset(
    {
        "market_summary",
        "skills_gap_summary",
        "capture_strategy",
        "application_strategy",
        "profile_strategy",
    }
)


class MarketIntelligenceExchangeImportResponse(BaseModel):
    context: GlobalAIContextOverlay
    preparation: MarketPreparationImportResponse


def _posting_evidence(session: Session) -> list[dict[str, Any]]:
    postings = session.scalars(
        select(Posting).order_by(Posting.created_at.desc(), Posting.id)
    ).all()
    jobs: list[dict[str, Any]] = []
    for posting in postings:
        cleaned = sanitize_capture_text(posting.description)
        jobs.append(
            {
                "posting_id": posting.id,
                "canonical_url": posting.canonical_url,
                "title": posting.title,
                "company": posting.company,
                "location": posting.location,
                "identity_status": posting.identity_status,
                "created_at": posting.created_at.isoformat(),
                "evidence_text": cleaned,
                "evidence_sha256": hashlib.sha256(cleaned.encode("utf-8")).hexdigest(),
            }
        )
    return jobs


def _capture_evidence(session: Session) -> list[dict[str, Any]]:
    captures = session.scalars(
        select(CaptureRun).order_by(CaptureRun.started_at.desc(), CaptureRun.id).limit(50)
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


def build_market_intelligence_exchange(session: Session) -> AIExchangeInput:
    context = build_global_context_snapshot()
    jobs = _posting_evidence(session)
    captures = _capture_evidence(session)
    return AIExchangeInput(
        generated_at=datetime.now(UTC),
        exchange_id=str(uuid4()),
        context_version=global_context_version(context),
        scope=AIExchangeScope(
            section="market_insights",
            analysis_types=["market_signal", "gap_signal", "recommendation", "context_update"],
            scope_label="JOLT target-market intelligence",
        ),
        context=context,
        evidence={
            "jobs": jobs,
            "capture_runs": captures,
            "counts": {
                "jobs": len(jobs),
                "capture_runs": len(captures),
            },
            "authority_notes": {
                "job_evidence": "Captured vacancy evidence only; no JOLT recommendation or ranking score is included.",
                "source_priority": "Vacancy body evidence outranks title/card/search metadata when they conflict.",
            },
        },
        protected_state={
            "patchable_context_namespaces": sorted(_MARKET_PATCH_KEYS),
            "non_patchable": [
                "job_search_preferences",
                "human_review_decisions",
                "applications",
            ],
        },
        requested_output={
            "feedback": {
                "market_signal": "Recurring role, geography, employment-model, compensation, or demand signals.",
                "gap_signal": "Recurring skills or evidence gaps supported by multiple vacancy observations.",
                "recommendation": "Concrete search, study, profile, or application actions with evidence_refs.",
            },
            "context_patch": (
                "Return only changed market_summary, skills_gap_summary, capture_strategy, "
                "application_strategy, or profile_strategy namespaces."
            ),
            "summary": "Include a concise executive_summary and high-confidence conclusions.",
        },
    )


def _apply_market_context_patch(output: AIExchangeOutput) -> GlobalAIContextOverlay:
    unknown = sorted(set(output.context_patch) - _MARKET_PATCH_KEYS)
    if unknown:
        raise ValueError(f"Market context patch contains non-patchable keys: {', '.join(unknown)}")

    current = load_global_ai_context()
    update = current.model_dump()
    for key, value in output.context_patch.items():
        if not isinstance(value, dict):
            raise ValueError(f"Market context namespace '{key}' must be an object")
        update[key] = value
    update["updated_at"] = output.reviewed_at
    update["updated_by"] = f"chatgpt:{output.review_version}"
    return save_global_ai_context(GlobalAIContextOverlay.model_validate(update))


def _feedback_action(payload: dict[str, Any], feedback_type: str) -> MarketPreparationAction:
    priority = payload.get("priority", "medium")
    if priority not in {"high", "medium", "low"}:
        priority = "medium"
    priority_value = cast(Literal["high", "medium", "low"], priority)
    return MarketPreparationAction(
        action_type=feedback_type,
        title=str(payload.get("title", ""))[:240],
        rationale=str(payload.get("rationale", "")),
        proposed_action=str(payload.get("proposed_action", "")),
        priority=priority_value,
        source="chatgpt_market_intelligence_exchange",
    )


def import_market_intelligence_exchange(
    output: AIExchangeOutput,
) -> MarketIntelligenceExchangeImportResponse:
    if output.scope.section != "market_insights":
        raise ValueError("Market Intelligence import requires scope.section=market_insights")

    context = _apply_market_context_patch(output)
    actions = [_feedback_action(item.payload, item.feedback_type) for item in output.feedback]
    executive_summary = output.summary.get("executive_summary", "")
    if not isinstance(executive_summary, str):
        executive_summary = json.dumps(executive_summary, ensure_ascii=False, sort_keys=True)
    preparation = import_market_preparation(
        MarketPreparationImportRequest(
            source="chatgpt_market_intelligence_exchange",
            summary=executive_summary,
            market_recommendations=actions,
            raw_payload=output.model_dump(mode="json"),
        )
    )
    return MarketIntelligenceExchangeImportResponse(
        context=context,
        preparation=preparation,
    )
