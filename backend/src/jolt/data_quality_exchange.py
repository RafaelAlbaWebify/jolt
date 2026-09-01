from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput, AIExchangeScope
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord, save_ai_exchange_feedback
from jolt.database import CaptureItem, CaptureRun, Posting, SourceDocument
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

_DATA_QUALITY_PATCH_KEYS = frozenset({"audit_summary", "capture_strategy"})
_DATA_QUALITY_ACTION_TYPES = {
    "data_quality_follow_up",
    "recapture",
    "identity_review",
    "provenance_review",
    "metadata_review",
    "cleanup_review",
}
_MAX_CAPTURE_RUNS = 25
_MAX_ITEMS_PER_RUN = 50
_MAX_POSTINGS = 150


class DataQualityExchangeImportResponse(BaseModel):
    context: GlobalAIContextOverlay
    feedback_record: AIExchangeFeedbackRecord
    actions: MarketPreparationImportResponse


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _capture_facts(session: Session) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runs = session.scalars(
        select(CaptureRun)
        .order_by(CaptureRun.started_at.desc(), CaptureRun.id)
        .limit(_MAX_CAPTURE_RUNS)
    ).all()
    run_rows: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for run in runs:
        items = session.scalars(
            select(CaptureItem)
            .where(CaptureItem.capture_run_id == run.id)
            .order_by(CaptureItem.id)
            .limit(_MAX_ITEMS_PER_RUN)
        ).all()
        persisted_count = session.scalar(
            select(func.count(CaptureItem.id)).where(CaptureItem.capture_run_id == run.id)
        )
        persisted_count = int(persisted_count or 0)
        if run.observed_item_count != persisted_count:
            findings.append(
                {
                    "finding_type": "capture_count_mismatch",
                    "capture_run_id": run.id,
                    "observed_item_count": run.observed_item_count,
                    "persisted_item_count": persisted_count,
                }
            )
        item_rows: list[dict[str, Any]] = []
        for item in items:
            reasons = json.loads(item.verification_reasons_json or "[]")
            linkage_valid = (
                item.detail_status == "verified"
                and bool(item.posting_id)
                and bool(item.source_document_id)
            ) or (
                item.detail_status == "rejected_unverified"
                and not item.posting_id
                and not item.source_document_id
            )
            if not linkage_valid:
                findings.append(
                    {
                        "finding_type": "capture_item_linkage_inconsistency",
                        "capture_run_id": run.id,
                        "capture_item_id": item.id,
                        "source_job_id": item.source_job_id,
                        "detail_status": item.detail_status,
                        "posting_id": item.posting_id,
                        "source_document_id": item.source_document_id,
                    }
                )
            item_rows.append(
                {
                    "capture_item_id": item.id,
                    "source_job_id": item.source_job_id,
                    "source_url": item.source_url,
                    "title": item.title,
                    "company": item.company,
                    "location": item.location,
                    "detail_status": item.detail_status,
                    "verification_reasons": reasons,
                    "posting_id": item.posting_id,
                    "source_document_id": item.source_document_id,
                    "linkage_structurally_valid": linkage_valid,
                }
            )
        run_rows.append(
            {
                "capture_run_id": run.id,
                "source": run.source,
                "mode": run.mode,
                "status": run.status,
                "search_url": run.search_url,
                "warnings": json.loads(run.warnings_json or "[]"),
                "requested_item_limit": run.requested_item_limit,
                "observed_item_count": run.observed_item_count,
                "persisted_item_count": persisted_count,
                "stop_reason": run.stop_reason,
                "started_at": run.started_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "items_sampled": len(items),
                "items": item_rows,
            }
        )
    return run_rows, findings


def _posting_facts(session: Session) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    postings = session.scalars(
        select(Posting).order_by(Posting.created_at.desc(), Posting.id).limit(_MAX_POSTINGS)
    ).all()
    rows: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for posting in postings:
        source = session.get(SourceDocument, posting.source_document_id)
        source_exists = source is not None
        stored_source_hash_valid = False
        description_matches_source = False
        source_text = ""
        if source is not None:
            source_text = sanitize_capture_text(source.raw_text)
            stored_source_hash_valid = source.content_hash == _sha256(source.raw_text)
            description_matches_source = sanitize_capture_text(posting.description) == source_text
            if not stored_source_hash_valid:
                findings.append(
                    {
                        "finding_type": "source_hash_mismatch",
                        "posting_id": posting.id,
                        "source_document_id": source.id,
                        "stored_hash": source.content_hash,
                        "computed_hash": _sha256(source.raw_text),
                    }
                )
            if not description_matches_source:
                findings.append(
                    {
                        "finding_type": "posting_source_text_divergence",
                        "posting_id": posting.id,
                        "source_document_id": source.id,
                    }
                )
        else:
            findings.append(
                {
                    "finding_type": "missing_source_document",
                    "posting_id": posting.id,
                    "source_document_id": posting.source_document_id,
                }
            )
        capture_items = session.scalars(
            select(CaptureItem)
            .where(CaptureItem.posting_id == posting.id)
            .order_by(CaptureItem.id.desc())
            .limit(5)
        ).all()
        metadata_observations = [
            {
                "capture_item_id": item.id,
                "title": item.title,
                "company": item.company,
                "location": item.location,
                "title_matches_posting": item.title.strip() == posting.title.strip(),
                "company_matches_posting": item.company.strip() == posting.company.strip(),
                "location_matches_posting": item.location.strip() == posting.location.strip(),
            }
            for item in capture_items
        ]
        if any(
            not observation["title_matches_posting"]
            or not observation["company_matches_posting"]
            or not observation["location_matches_posting"]
            for observation in metadata_observations
        ):
            findings.append(
                {
                    "finding_type": "capture_posting_metadata_divergence",
                    "posting_id": posting.id,
                    "observations": metadata_observations,
                }
            )
        rows.append(
            {
                "posting_id": posting.id,
                "canonical_url": posting.canonical_url,
                "identity_key": posting.identity_key,
                "identity_status": posting.identity_status,
                "title": posting.title,
                "company": posting.company,
                "location": posting.location,
                "created_at": posting.created_at.isoformat(),
                "source_document_id": posting.source_document_id,
                "source_exists": source_exists,
                "source_hash_valid": stored_source_hash_valid,
                "posting_description_matches_source": description_matches_source,
                "source_evidence_text": source_text,
                "source_evidence_sha256": _sha256(source_text),
                "metadata_observations": metadata_observations,
            }
        )
    return rows, findings


def build_data_quality_exchange(session: Session) -> AIExchangeInput:
    context = build_global_context_snapshot()
    capture_runs, capture_findings = _capture_facts(session)
    postings, posting_findings = _posting_facts(session)
    findings = [*capture_findings, *posting_findings]
    finding_counts = Counter(str(item.get("finding_type", "unknown")) for item in findings)
    return AIExchangeInput(
        generated_at=datetime.now(UTC),
        exchange_id=str(uuid4()),
        context_version=global_context_version(context),
        scope=AIExchangeScope(
            section="data_quality",
            analysis_types=["audit_result", "recommendation", "context_update", "correction"],
            scope_label="JOLT deterministic integrity facts and source-evidence quality",
        ),
        context=context,
        evidence={
            "capture_runs": capture_runs,
            "postings": postings,
            "deterministic_findings": findings,
            "counts": {
                "capture_runs": len(capture_runs),
                "postings": len(postings),
                "deterministic_findings": len(findings),
                "finding_types": dict(sorted(finding_counts.items())),
            },
            "authority_notes": {
                "deterministic_facts": (
                    "Hashes, counts, linkage presence, exact metadata equality, and exact cleaned-text equality are deterministic facts."
                ),
                "semantic_authority": (
                    "JOLT does not decide whether a deterministic difference is meaningful. ChatGPT must interpret significance from source evidence and context."
                ),
                "source_priority": "Raw source/body evidence outranks card/title/search metadata when they conflict.",
                "immutability": "Raw capture items, source documents, postings, human decisions, applications, and preferences are not patchable here.",
            },
        },
        protected_state={
            "patchable_context_namespaces": sorted(_DATA_QUALITY_PATCH_KEYS),
            "non_patchable": [
                "capture_runs",
                "capture_items",
                "source_documents",
                "postings",
                "job_search_preferences",
                "human_review_decisions",
                "applications",
            ],
        },
        requested_output={
            "feedback": {
                "audit_result": (
                    "Interpret deterministic findings and source evidence. Distinguish harmless drift, expected normalization, stale evidence, provenance risk, identity ambiguity, and material data defects."
                ),
                "correction": (
                    "Describe a correction only when evidence supports it; never directly rewrite protected raw evidence."
                ),
                "recommendation": (
                    "For importable follow-up actions include action_type, title, rationale, proposed_action, priority, and evidence_refs. "
                    "action_type must be one of data_quality_follow_up, recapture, identity_review, provenance_review, metadata_review, or cleanup_review."
                ),
            },
            "context_patch": "Return only changed audit_summary or capture_strategy namespaces.",
            "summary": "Include executive_summary, material_findings, benign_differences, repair_priorities, and evidence_gaps.",
        },
    )


def _apply_data_quality_context_patch(output: AIExchangeOutput) -> GlobalAIContextOverlay:
    unknown = sorted(set(output.context_patch) - _DATA_QUALITY_PATCH_KEYS)
    if unknown:
        raise ValueError(
            f"Data quality context patch contains non-patchable keys: {', '.join(unknown)}"
        )
    current = load_global_ai_context()
    update = current.model_dump()
    for key, value in output.context_patch.items():
        if not isinstance(value, dict):
            raise ValueError(f"Data quality context namespace '{key}' must be an object")
        update[key] = value
    update["updated_at"] = output.reviewed_at
    update["updated_by"] = f"chatgpt:{output.review_version}"
    return save_global_ai_context(GlobalAIContextOverlay.model_validate(update))


def _data_quality_actions(output: AIExchangeOutput) -> list[MarketPreparationAction]:
    actions: list[MarketPreparationAction] = []
    for feedback in output.feedback:
        if feedback.feedback_type != "recommendation":
            continue
        payload = feedback.payload
        raw_type = payload.get("action_type")
        if raw_type not in _DATA_QUALITY_ACTION_TYPES:
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
                title=str(payload.get("title", ""))[:240] or "Review data-quality finding",
                rationale=rationale,
                proposed_action=str(payload.get("proposed_action", "")),
                priority=priority,
                status="pending",
                source="chatgpt_data_quality_exchange",
            )
        )
    return actions


def import_data_quality_exchange(output: AIExchangeOutput) -> DataQualityExchangeImportResponse:
    if output.scope.section != "data_quality":
        raise ValueError("Data quality import requires scope.section=data_quality")
    context = _apply_data_quality_context_patch(output)
    feedback_record = save_ai_exchange_feedback(output)
    executive_summary = output.summary.get("executive_summary", "")
    if not isinstance(executive_summary, str):
        executive_summary = json.dumps(executive_summary, ensure_ascii=False, sort_keys=True)
    actions = import_market_preparation(
        MarketPreparationImportRequest(
            source="chatgpt_data_quality_exchange",
            summary=executive_summary,
            market_recommendations=_data_quality_actions(output),
            raw_payload=output.model_dump(mode="json"),
        )
    )
    return DataQualityExchangeImportResponse(
        context=context,
        feedback_record=feedback_record,
        actions=actions,
    )
