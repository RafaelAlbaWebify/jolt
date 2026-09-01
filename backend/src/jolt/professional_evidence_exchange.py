from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput, AIExchangeScope
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord, save_ai_exchange_feedback
from jolt.global_context import (
    GlobalAIContextOverlay,
    build_global_context_snapshot,
    global_context_version,
    load_global_ai_context,
    save_global_ai_context,
)
from jolt.professional_intelligence_evidence_review import (
    ProfessionalEvidenceRunReview,
    review_professional_capture_evidence,
)
from jolt.professional_intelligence_records import ProfessionalCaptureRun

_PROFESSIONAL_PATCH_KEYS = frozenset(
    {"professional_evidence_summary", "profile_strategy", "audit_summary"}
)
_MAX_REVIEWED_RUNS = 3
_MAX_RENDERED_TEXT_CHARS = 120_000
_MAX_OTHER_CONTENT_CHARS = 20_000


class ProfessionalEvidenceExchangeImportResponse(BaseModel):
    context: GlobalAIContextOverlay
    feedback_record: AIExchangeFeedbackRecord


def _bounded_content(content: object, *, artifact_type: str) -> tuple[object, bool]:
    if content is None:
        return None, False
    if artifact_type == "rendered_text_json" and isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            truncated = len(text) > _MAX_RENDERED_TEXT_CHARS
            compact = dict(content)
            compact["text"] = text[:_MAX_RENDERED_TEXT_CHARS]
            return compact, truncated
    rendered = json.dumps(content, ensure_ascii=False, sort_keys=True)
    truncated = len(rendered) > _MAX_OTHER_CONTENT_CHARS
    if not truncated:
        return content, False
    return rendered[:_MAX_OTHER_CONTENT_CHARS], True


def _review_evidence(review: ProfessionalEvidenceRunReview) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for source in review.sources:
        artifacts: list[dict[str, Any]] = []
        for artifact in source.artifacts:
            if not artifact.integrity_valid or not artifact.reviewable:
                continue
            bounded, truncated = _bounded_content(
                artifact.content,
                artifact_type=artifact.artifact_type,
            )
            artifacts.append(
                {
                    "artifact_id": artifact.id,
                    "artifact_type": artifact.artifact_type,
                    "relative_path": artifact.relative_path,
                    "completeness_status": artifact.completeness_status,
                    "integrity_valid": artifact.integrity_valid,
                    "content": bounded,
                    "content_truncated": truncated,
                }
            )
        sources.append(
            {
                "source_id": source.source_id,
                "completeness_status": source.completeness_status,
                "artifacts": artifacts,
            }
        )
    return {
        "capture_run_id": review.capture_run_id,
        "run_status": review.run_status,
        "integrity_valid": review.integrity_valid,
        "ready_for_analysis": review.ready_for_analysis,
        "sources": sources,
    }


def _professional_evidence(session: Session) -> dict[str, Any]:
    runs = session.scalars(
        select(ProfessionalCaptureRun)
        .order_by(ProfessionalCaptureRun.requested_at.desc(), ProfessionalCaptureRun.id)
        .limit(10)
    ).all()
    run_summaries = [
        {
            "capture_run_id": run.id,
            "mode": run.mode,
            "status": run.status,
            "completed_source_count": run.completed_source_count,
            "requested_at": run.requested_at.isoformat(),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "stop_reason": run.stop_reason,
        }
        for run in runs
    ]
    reviewed: list[dict[str, Any]] = []
    review_errors: list[dict[str, str]] = []
    terminal = [run for run in runs if run.status in {"completed", "completed_with_gaps"}]
    for run in terminal[:_MAX_REVIEWED_RUNS]:
        try:
            review = review_professional_capture_evidence(session, run.id)
        except ValueError as exc:
            review_errors.append({"capture_run_id": run.id, "reason": str(exc)})
            continue
        reviewed.append(_review_evidence(review))
    return {
        "capture_runs": run_summaries,
        "verified_reviews": reviewed,
        "review_errors": review_errors,
        "counts": {
            "capture_runs": len(runs),
            "verified_reviews": len(reviewed),
            "review_errors": len(review_errors),
        },
        "authority_notes": {
            "integrity": (
                "Only artifacts marked integrity_valid and reviewable by JOLT are exported as professional evidence content."
            ),
            "reasoning": (
                "Deterministic term extraction is intentionally excluded. ChatGPT must interpret the verified source content directly."
            ),
            "claims": (
                "Treat explicit source statements as evidence. Do not upgrade mentions, training, or project exposure into unsupported professional experience."
            ),
            "truncation": (
                "content_truncated=true means the source was deterministically bounded for exchange size; do not assume omitted content."
            ),
        },
    }


def build_professional_evidence_exchange(session: Session) -> AIExchangeInput:
    context = build_global_context_snapshot()
    return AIExchangeInput(
        generated_at=datetime.now(UTC),
        exchange_id=str(uuid4()),
        context_version=global_context_version(context),
        scope=AIExchangeScope(
            section="professional_evidence",
            analysis_types=["extraction", "recommendation", "context_update", "audit_result"],
            scope_label="JOLT integrity-verified professional evidence",
        ),
        context=context,
        evidence=_professional_evidence(session),
        protected_state={
            "patchable_context_namespaces": sorted(_PROFESSIONAL_PATCH_KEYS),
            "non_patchable": [
                "professional_capture_runs",
                "professional_artifacts",
                "job_search_preferences",
                "human_review_decisions",
                "applications",
            ],
        },
        requested_output={
            "feedback": {
                "extraction": (
                    "Extract evidence-backed capabilities, projects, responsibilities, certifications, and credibility boundaries."
                ),
                "audit_result": (
                    "Flag unsupported claims, weak evidence, contradictions, stale evidence, or areas needing stronger proof."
                ),
                "recommendation": (
                    "Recommend manual evidence, portfolio, CV, LinkedIn, or interview-positioning actions with evidence_refs."
                ),
            },
            "context_patch": (
                "Return only changed professional_evidence_summary, profile_strategy, or audit_summary namespaces."
            ),
            "summary": "Include executive_summary, strongest_evidence, credibility_boundaries, and evidence_gaps.",
        },
    )


def _apply_professional_context_patch(output: AIExchangeOutput) -> GlobalAIContextOverlay:
    unknown = sorted(set(output.context_patch) - _PROFESSIONAL_PATCH_KEYS)
    if unknown:
        raise ValueError(
            f"Professional evidence context patch contains non-patchable keys: {', '.join(unknown)}"
        )
    current = load_global_ai_context()
    update = current.model_dump()
    for key, value in output.context_patch.items():
        if not isinstance(value, dict):
            raise ValueError(f"Professional evidence context namespace '{key}' must be an object")
        update[key] = value
    update["updated_at"] = output.reviewed_at
    update["updated_by"] = f"chatgpt:{output.review_version}"
    return save_global_ai_context(GlobalAIContextOverlay.model_validate(update))


def import_professional_evidence_exchange(
    output: AIExchangeOutput,
) -> ProfessionalEvidenceExchangeImportResponse:
    if output.scope.section != "professional_evidence":
        raise ValueError(
            "Professional evidence import requires scope.section=professional_evidence"
        )
    context = _apply_professional_context_patch(output)
    feedback_record = save_ai_exchange_feedback(output)
    return ProfessionalEvidenceExchangeImportResponse(
        context=context,
        feedback_record=feedback_record,
    )
