from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput, AIExchangeScope
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord, save_ai_exchange_feedback
from jolt.database import CaptureItem, CaptureRun, Posting, SourceDocument
from jolt.global_context import (
    GlobalAIContextOverlay,
    build_global_context_snapshot,
    global_context_version,
    load_global_ai_context,
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
_MARKET_CORPUS_DAYS = 90
_MARKET_CORPUS_LIMIT = 500


class MarketIntelligenceExchangeImportResponse(BaseModel):
    context: GlobalAIContextOverlay
    feedback_record: AIExchangeFeedbackRecord
    recommendation_count: int


def _posting_evidence(session: Session) -> list[dict[str, Any]]:
    cutoff = datetime.now(UTC) - timedelta(days=_MARKET_CORPUS_DAYS)
    rows = session.execute(
        select(CaptureItem, CaptureRun, SourceDocument, Posting)
        .join(CaptureRun, CaptureRun.id == CaptureItem.capture_run_id)
        .join(SourceDocument, SourceDocument.id == CaptureItem.source_document_id)
        .join(Posting, Posting.id == CaptureItem.posting_id)
        .where(CaptureItem.detail_status == "verified")
        .where(CaptureRun.status != "running")
        .where(CaptureRun.started_at >= cutoff)
        .order_by(CaptureRun.started_at.desc(), CaptureItem.id.desc())
        .limit(_MARKET_CORPUS_LIMIT)
    ).all()

    jobs: list[dict[str, Any]] = []
    for item, capture, source, posting in rows:
        cleaned = sanitize_capture_text(source.raw_text)
        jobs.append(
            {
                "capture_run_id": capture.id,
                "source_job_id": item.source_job_id,
                "capture_item_id": item.id,
                "source_document_id": source.id,
                "posting_id": posting.id,
                "posting_identity_key": posting.identity_key,
                "source_url": source.source_url or item.source_url,
                "canonical_url": posting.canonical_url,
                "title": item.title or posting.title,
                "company": item.company or posting.company,
                "location": item.location or posting.location,
                "identity_status": posting.identity_status,
                "captured_at": source.captured_at.isoformat(),
                "evidence_text": cleaned,
                "evidence_sha256": hashlib.sha256(cleaned.encode("utf-8")).hexdigest(),
            }
        )
    return jobs


def _capture_evidence(session: Session, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    capture_ids = list(dict.fromkeys(str(job["capture_run_id"]) for job in jobs))
    if not capture_ids:
        return []
    captures = session.scalars(
        select(CaptureRun)
        .where(CaptureRun.id.in_(capture_ids))
        .order_by(CaptureRun.started_at.desc(), CaptureRun.id)
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
    captures = _capture_evidence(session, jobs)
    captured_times = [str(job["captured_at"]) for job in jobs]
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
            "counts": {"jobs": len(jobs), "capture_runs": len(captures)},
            "corpus_policy": {
                "window_days": _MARKET_CORPUS_DAYS,
                "max_verified_observations": _MARKET_CORPUS_LIMIT,
                "oldest_included_at": min(captured_times) if captured_times else None,
                "newest_included_at": max(captured_times) if captured_times else None,
            },
            "authority_notes": {
                "job_evidence": (
                    "Verified source-document evidence only; no local JOLT recommendation, fit score, "
                    "ranking score, or evaluation reason is included."
                ),
                "source_priority": (
                    "Vacancy body evidence outranks title/card/search metadata when they conflict. "
                    "Listing country alone is not an eligibility decision."
                ),
                "duplicates": (
                    "Repeated observations may represent real repeated market exposure. Use posting_identity_key "
                    "to distinguish market frequency from unique opportunities."
                ),
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
                "recommendation": "Concrete manual search, study, profile, or application action with evidence_refs.",
            },
            "context_patch": (
                "For the unified work-package workflow, put durable market_summary, skills_gap_summary, "
                "capture_strategy, application_strategy, or profile_strategy changes in the package's "
                "top-level context_patch. Section-level context_patch must remain empty."
            ),
            "summary": "Include a concise executive_summary and high-confidence conclusions.",
        },
    )


def _validate_market_output(output: AIExchangeOutput) -> None:
    if output.scope.section != "market_insights":
        raise ValueError("Market Intelligence import requires scope.section=market_insights")
    if output.context_patch:
        raise ValueError(
            "Market section context_patch must be empty; use the unified work package top-level context_patch"
        )
    for item in output.feedback:
        if item.feedback_type != "recommendation":
            continue
        title = item.payload.get("title")
        proposed_action = item.payload.get("proposed_action")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Market recommendation feedback requires a non-empty title")
        if not isinstance(proposed_action, str) or not proposed_action.strip():
            raise ValueError("Market recommendation feedback requires a non-empty proposed_action")


def import_market_intelligence_exchange(
    output: AIExchangeOutput,
) -> MarketIntelligenceExchangeImportResponse:
    _validate_market_output(output)
    feedback_record = save_ai_exchange_feedback(output)
    recommendation_count = sum(
        1 for item in output.feedback if item.feedback_type == "recommendation"
    )
    return MarketIntelligenceExchangeImportResponse(
        context=load_global_ai_context(),
        feedback_record=feedback_record,
        recommendation_count=recommendation_count,
    )
