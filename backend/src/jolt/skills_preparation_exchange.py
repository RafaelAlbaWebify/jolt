from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput, AIExchangeScope
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord, save_ai_exchange_feedback
from jolt.database import LinkedInPresenceCapture, Posting
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

_SKILLS_PATCH_KEYS = frozenset({"skills_gap_summary", "audit_summary"})
_ACTION_TYPES = {
    "study",
    "practice",
    "proof_of_work",
    "interview_prep",
}
_MAX_VACANCIES = 300


class SkillsPreparationExchangeImportResponse(BaseModel):
    context: GlobalAIContextOverlay
    feedback_record: AIExchangeFeedbackRecord
    preparation: MarketPreparationImportResponse


def _vacancy_evidence(session: Session) -> tuple[list[dict[str, Any]], int]:
    total = int(session.scalar(select(func.count(Posting.id))) or 0)
    postings = session.scalars(
        select(Posting)
        .order_by(Posting.created_at.desc(), Posting.id)
        .limit(_MAX_VACANCIES)
    ).all()
    evidence: list[dict[str, Any]] = []
    for posting in postings:
        text = sanitize_capture_text(posting.description)
        evidence.append(
            {
                "posting_id": posting.id,
                "title": posting.title,
                "company": posting.company,
                "location": posting.location,
                "canonical_url": posting.canonical_url,
                "created_at": posting.created_at.isoformat(),
                "evidence_text": text,
                "evidence_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    return evidence, total


def _profile_evidence(session: Session) -> list[dict[str, Any]]:
    captures = session.scalars(
        select(LinkedInPresenceCapture)
        .where(LinkedInPresenceCapture.category.in_(["profile", "public_profile"]))
        .order_by(LinkedInPresenceCapture.captured_at.desc(), LinkedInPresenceCapture.id)
        .limit(20)
    ).all()
    return [
        {
            "capture_id": capture.id,
            "category": capture.category,
            "title": capture.title,
            "source_url": capture.source_url,
            "visible_text": capture.visible_text,
            "notes": capture.notes,
            "captured_at": capture.captured_at.isoformat(),
            "changed_since_previous": capture.changed_since_previous,
        }
        for capture in captures
    ]


def build_skills_preparation_exchange(session: Session) -> AIExchangeInput:
    context = build_global_context_snapshot()
    vacancies, available_vacancies = _vacancy_evidence(session)
    profile = _profile_evidence(session)
    omitted_vacancies = max(0, available_vacancies - len(vacancies))
    return AIExchangeInput(
        generated_at=datetime.now(UTC),
        exchange_id=str(uuid4()),
        context_version=global_context_version(context),
        scope=AIExchangeScope(
            section="skills_gaps",
            analysis_types=["gap_signal", "recommendation", "context_update", "audit_result"],
            scope_label="JOLT skills demand, demonstrated evidence, and preparation priorities",
        ),
        context=context,
        evidence={
            "vacancies": vacancies,
            "profile_evidence": profile,
            "counts": {
                "vacancies": len(vacancies),
                "profile_captures": len(profile),
                "available_vacancies": available_vacancies,
                "omitted_vacancies": omitted_vacancies,
            },
            "corpus_policy": {
                "max_recent_vacancies": _MAX_VACANCIES,
                "available_vacancies": available_vacancies,
                "exported_vacancies": len(vacancies),
                "omitted_vacancies": omitted_vacancies,
                "ordering": "newest_postings_first",
                "omission_meaning": (
                    "Older historical postings beyond the deterministic cap are omitted from this "
                    "supporting skills corpus only. Current Review Inbox vacancies are not affected."
                ),
            },
            "authority_notes": {
                "vacancies": "Raw captured vacancy evidence is authoritative for stated requirements.",
                "profile": "Profile captures are evidence of represented skills, not proof of every real capability.",
                "local_gap_logic": (
                    "JOLT keyword-derived learning signals, ranking scores, recommendations, and local gap judgments "
                    "are intentionally excluded. ChatGPT must infer gaps from exported evidence."
                ),
                "uncertainty": "Absence from profile evidence does not prove absence of capability; mark unsupported conclusions as uncertain.",
            },
        },
        protected_state={
            "patchable_context_namespaces": sorted(_SKILLS_PATCH_KEYS),
            "non_patchable": [
                "job_search_preferences",
                "profile_captures",
                "human_review_decisions",
                "applications",
                "outcomes",
            ],
        },
        requested_output={
            "feedback": {
                "gap_signal": (
                    "Identify recurring requirements and compare them with represented evidence. Distinguish "
                    "demonstrated coverage, partial evidence, genuine gap, and insufficient evidence."
                ),
                "recommendation": (
                    "For actionable preparation recommendations use action_type study, practice, proof_of_work, "
                    "or interview_prep plus title, rationale, proposed_action, priority, and evidence_refs."
                ),
            },
            "context_patch": "Return only changed skills_gap_summary or audit_summary namespaces.",
            "summary": "Include executive_summary, highest_leverage_gaps, covered_strengths, and insufficient_evidence.",
        },
    )


def _apply_skills_context_patch(output: AIExchangeOutput) -> GlobalAIContextOverlay:
    unknown = sorted(set(output.context_patch) - _SKILLS_PATCH_KEYS)
    if unknown:
        raise ValueError(f"Skills context patch contains non-patchable keys: {', '.join(unknown)}")
    current = load_global_ai_context()
    update = current.model_dump()
    for key, value in output.context_patch.items():
        if not isinstance(value, dict):
            raise ValueError(f"Skills context namespace '{key}' must be an object")
        update[key] = value
    update["updated_at"] = output.reviewed_at
    update["updated_by"] = f"chatgpt:{output.review_version}"
    return save_global_ai_context(GlobalAIContextOverlay.model_validate(update))


def _preparation_actions(output: AIExchangeOutput) -> list[MarketPreparationAction]:
    actions: list[MarketPreparationAction] = []
    for feedback in output.feedback:
        if feedback.feedback_type != "recommendation":
            continue
        payload = feedback.payload
        raw_action_type = payload.get("action_type")
        if raw_action_type not in _ACTION_TYPES:
            continue
        raw_priority = payload.get("priority", "medium")
        if raw_priority not in {"high", "medium", "low"}:
            raw_priority = "medium"
        priority = cast(Literal["high", "medium", "low"], raw_priority)
        evidence_refs = feedback.evidence_refs
        rationale = str(payload.get("rationale", ""))
        if evidence_refs:
            rationale = f"{rationale}\nEvidence: {', '.join(evidence_refs)}".strip()
        actions.append(
            MarketPreparationAction(
                action_type=str(raw_action_type),
                title=str(payload.get("title", ""))[:240] or "Review preparation priority",
                rationale=rationale,
                proposed_action=str(payload.get("proposed_action", "")),
                priority=priority,
                status="pending",
                source="chatgpt_skills_preparation_exchange",
            )
        )
    return actions


def import_skills_preparation_exchange(
    output: AIExchangeOutput,
) -> SkillsPreparationExchangeImportResponse:
    if output.scope.section != "skills_gaps":
        raise ValueError("Skills preparation import requires scope.section=skills_gaps")

    context = _apply_skills_context_patch(output)
    feedback_record = save_ai_exchange_feedback(output)
    executive_summary = output.summary.get("executive_summary", "")
    if not isinstance(executive_summary, str):
        executive_summary = json.dumps(executive_summary, ensure_ascii=False, sort_keys=True)
    preparation = import_market_preparation(
        MarketPreparationImportRequest(
            source="chatgpt_skills_preparation_exchange",
            summary=executive_summary,
            preparation_plan=_preparation_actions(output),
            raw_payload=output.model_dump(mode="json"),
        )
    )
    return SkillsPreparationExchangeImportResponse(
        context=context,
        feedback_record=feedback_record,
        preparation=preparation,
    )
