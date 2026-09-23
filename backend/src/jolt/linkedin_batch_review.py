from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.ai_review_import import AIReviewJob, MandatoryRequirementResult
from jolt.ai_review_pack import _analysis_text
from jolt.database import (
    AIReview,
    Application,
    CaptureItem,
    LinkedInDiscoveryBatch,
    LinkedInDiscoveryBatchReviewItem,
    LinkedInDiscoveryBatchSearch,
    Posting,
    ReviewDecision,
    SourceDocument,
    utc_now,
)
from jolt.errors import JoltNotFoundError
from jolt.hardline_evidence import analyze_location_evidence
from jolt.preference_aware_evaluation import sanitize_capture_text

BATCH_REVIEW_CONTRACT_TYPE = "jolt_ai_review_batch"
BATCH_REVIEW_CONTRACT_VERSION = "1.0"
AI_REVIEW_CONTRACT_VERSION = "1.1"


class BatchAIReviewImportRequest(BaseModel):
    contract_type: Literal["jolt_ai_review_batch"]
    contract_version: Literal["1.0"]
    ai_review_contract_version: Literal["1.1"]
    discovery_batch_id: str = Field(min_length=1)
    review_source: Literal["chatgpt_source_first"]
    review_version: str = Field(min_length=1, max_length=80)
    reviewed_at: datetime
    jobs: list[AIReviewJob]

    @model_validator(mode="after")
    def require_hardline_fields(self) -> BatchAIReviewImportRequest:
        required_fields = {
            "hardline_status",
            "hardline_reasons",
            "location_eligibility",
            "location_evidence",
            "mandatory_requirements",
            "mandatory_requirement_results",
            "employment_constraints",
            "fit_analysis_allowed",
            "technical_fit_percent",
            "final_decision",
            "decision_reason",
        }
        for job in self.jobs:
            missing = required_fields - job.model_fields_set
            if missing:
                raise ValueError(
                    "Batch AI review is missing hardline fields: "
                    + ", ".join(sorted(missing))
                )
            if job.final_decision in {"strong_pursue", "pursue"}:
                if job.hardline_status != "PASS":
                    raise ValueError("Positive decisions require hardline_status=PASS")
                if job.location_eligibility != "eligible":
                    raise ValueError(
                        "Positive decisions require location_eligibility=eligible"
                    )
        return self


class BatchAIReviewImportResponse(BaseModel):
    discovery_batch_id: str
    received_count: int
    created_count: int
    updated_count: int
    protected_human_state_count: int


def _batch_capture_ids(session: Session, batch_id: str) -> list[str]:
    return [
        capture_run_id
        for capture_run_id in session.scalars(
            select(LinkedInDiscoveryBatchSearch.capture_run_id)
            .where(
                LinkedInDiscoveryBatchSearch.batch_id == batch_id,
                LinkedInDiscoveryBatchSearch.status == "completed",
                LinkedInDiscoveryBatchSearch.capture_run_id.is_not(None),
            )
            .order_by(LinkedInDiscoveryBatchSearch.position.asc())
        ).all()
        if capture_run_id is not None
    ]


def _batch_items(session: Session, batch_id: str) -> list[CaptureItem]:
    capture_ids = _batch_capture_ids(session, batch_id)
    if not capture_ids:
        return []
    search_positions = {
        search.capture_run_id: search.position
        for search in session.scalars(
            select(LinkedInDiscoveryBatchSearch).where(
                LinkedInDiscoveryBatchSearch.batch_id == batch_id,
                LinkedInDiscoveryBatchSearch.capture_run_id.is_not(None),
            )
        ).all()
        if search.capture_run_id is not None
    }
    items = list(
        session.scalars(
            select(CaptureItem).where(
                CaptureItem.capture_run_id.in_(capture_ids),
                CaptureItem.posting_id.is_not(None),
            )
        ).all()
    )
    return sorted(
        items,
        key=lambda item: (
            search_positions.get(item.capture_run_id, 10**9),
            item.id,
        ),
    )


def materialize_batch_review_set(
    session: Session,
    batch_id: str,
) -> list[LinkedInDiscoveryBatchReviewItem]:
    batch = session.get(LinkedInDiscoveryBatch, batch_id)
    if batch is None:
        raise JoltNotFoundError("LinkedIn discovery batch was not found.")
    if batch.status not in {"completed", "completed_with_failures"}:
        raise ValueError("Discovery batch must be completed before AI review export.")

    existing = list(
        session.scalars(
            select(LinkedInDiscoveryBatchReviewItem)
            .where(LinkedInDiscoveryBatchReviewItem.batch_id == batch_id)
            .order_by(LinkedInDiscoveryBatchReviewItem.position.asc())
        ).all()
    )
    if existing:
        return existing

    items = _batch_items(session, batch_id)
    if not items:
        raise ValueError("Discovery batch contains no completed captured postings.")

    posting_ids = {item.posting_id for item in items if item.posting_id is not None}
    reviewed_posting_ids = set(
        session.scalars(
            select(AIReview.posting_id).where(AIReview.posting_id.in_(posting_ids))
        ).all()
    )

    seen: set[str] = set()
    position = 0
    for item in items:
        posting_id = item.posting_id
        if posting_id is None or posting_id in seen or posting_id in reviewed_posting_ids:
            continue
        seen.add(posting_id)
        position += 1
        session.add(
            LinkedInDiscoveryBatchReviewItem(
                id=str(uuid4()),
                batch_id=batch_id,
                posting_id=posting_id,
                representative_capture_run_id=item.capture_run_id,
                representative_capture_item_id=item.id,
                representative_source_job_id=item.source_job_id,
                position=position,
                created_at=utc_now(),
            )
        )

    session.commit()
    return list(
        session.scalars(
            select(LinkedInDiscoveryBatchReviewItem)
            .where(LinkedInDiscoveryBatchReviewItem.batch_id == batch_id)
            .order_by(LinkedInDiscoveryBatchReviewItem.position.asc())
        ).all()
    )


def _posting_occurrences(
    session: Session,
    *,
    batch_id: str,
    posting_id: str,
) -> list[dict[str, object]]:
    searches = list(
        session.scalars(
            select(LinkedInDiscoveryBatchSearch).where(
                LinkedInDiscoveryBatchSearch.batch_id == batch_id,
                LinkedInDiscoveryBatchSearch.capture_run_id.is_not(None),
            )
        ).all()
    )
    by_capture = {
        search.capture_run_id: search
        for search in searches
        if search.capture_run_id is not None
    }
    items = list(
        session.scalars(
            select(CaptureItem).where(
                CaptureItem.capture_run_id.in_(list(by_capture)),
                CaptureItem.posting_id == posting_id,
            )
        ).all()
    )
    items.sort(key=lambda item: (by_capture[item.capture_run_id].position, item.id))
    return [
        {
            "capture_run_id": item.capture_run_id,
            "capture_item_id": item.id,
            "source_job_id": item.source_job_id,
            "search_position": by_capture[item.capture_run_id].position,
            "search_label": by_capture[item.capture_run_id].label_snapshot,
            "search_url": by_capture[item.capture_run_id].search_url_snapshot,
        }
        for item in items
    ]


def _response_template(batch_id: str) -> dict[str, object]:
    return {
        "contract_type": BATCH_REVIEW_CONTRACT_TYPE,
        "contract_version": BATCH_REVIEW_CONTRACT_VERSION,
        "ai_review_contract_version": AI_REVIEW_CONTRACT_VERSION,
        "discovery_batch_id": batch_id,
        "review_source": "chatgpt_source_first",
        "review_version": "<AI review version>",
        "reviewed_at": "<ISO-8601 timestamp>",
        "jobs": [
            {
                "posting_id": "<posting_id from jobs>",
                "source_job_id": "<representative_source_job_id>",
                "hardline_status": "PASS|REJECT|MANUAL_REVIEW",
                "hardline_reasons": [],
                "location_eligibility": "eligible|conditional|ineligible|unknown",
                "location_evidence": [],
                "mandatory_requirements": [],
                "mandatory_requirement_results": [],
                "employment_constraints": [],
                "fit_analysis_allowed": True,
                "technical_fit_percent": None,
                "final_decision": "strong_pursue|pursue|conditional|reject",
                "decision_reason": "",
                "decision": "strong_pursue|pursue|conditional|reject",
                "priority_score": 0,
                "geography_status": "eligible|conditional|ineligible|unknown",
                "clearance_status": "clear|conditional|blocked|unknown",
                "language_status": "clear|conditional|blocked|unknown",
                "technical_fit": None,
                "duplicate_of_posting_id": None,
                "summary": "",
                "reasons": [],
            }
        ],
    }


def build_batch_ai_review_document(session: Session, batch_id: str) -> dict[str, object]:
    review_items = materialize_batch_review_set(session, batch_id)
    all_items = _batch_items(session, batch_id)
    unique_posting_ids = {
        item.posting_id for item in all_items if item.posting_id is not None
    }

    posting_ids = [item.posting_id for item in review_items]
    postings = {
        posting.id: posting
        for posting in session.scalars(
            select(Posting).where(Posting.id.in_(posting_ids))
        ).all()
    } if posting_ids else {}

    source_ids = {posting.source_document_id for posting in postings.values()}
    sources = {
        source.id: source
        for source in session.scalars(
            select(SourceDocument).where(SourceDocument.id.in_(source_ids))
        ).all()
    } if source_ids else {}

    jobs: list[dict[str, object]] = []
    for review_item in review_items:
        posting = postings[review_item.posting_id]
        source = sources.get(posting.source_document_id)
        source_raw_text = source.raw_text if source is not None else ""
        location_signals = analyze_location_evidence(
            location=posting.location,
            source_text=source_raw_text or posting.description,
        )
        jobs.append(
            {
                "posting_id": posting.id,
                "source_job_id": review_item.representative_source_job_id,
                "representative_capture_run_id": review_item.representative_capture_run_id,
                "representative_capture_item_id": review_item.representative_capture_item_id,
                "occurrences": _posting_occurrences(
                    session,
                    batch_id=batch_id,
                    posting_id=posting.id,
                ),
                "canonical_url": posting.canonical_url,
                "title": posting.title,
                "company": posting.company,
                "location": posting.location,
                "location_hardline_evidence": {
                    "location_eligibility": location_signals.location_eligibility,
                    "hardline_reject": location_signals.hardline_reject,
                    "positive_evidence": list(location_signals.positive_evidence),
                    "negative_evidence": list(location_signals.negative_evidence),
                },
                "identity_status": posting.identity_status,
                "source_document_id": posting.source_document_id,
                "description_clean": sanitize_capture_text(posting.description),
                "source_text_clean": sanitize_capture_text(source_raw_text),
                "analysis_text": _analysis_text(
                    title=posting.title,
                    company=posting.company,
                    location=posting.location,
                    description=posting.description,
                    source_raw_text=source_raw_text,
                ),
                "audit": {
                    "source_raw_text": source_raw_text,
                    "source_raw_text_sha256": hashlib.sha256(
                        source_raw_text.encode("utf-8")
                    ).hexdigest(),
                },
            }
        )

    return {
        "pack_type": "jolt_ai_review_batch_input",
        "pack_version": "1.0",
        "review_contract_version": AI_REVIEW_CONTRACT_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(),
        "discovery_batch_id": batch_id,
        "classification_authority": "external_ai",
        "jolt_decisions_included": False,
        "jolt_scores_included": False,
        "counts": {
            "raw_capture_items": len(all_items),
            "unique_canonical_postings": len(unique_posting_ids),
            "already_reviewed_excluded": len(unique_posting_ids) - len(review_items),
            "review_set": len(review_items),
        },
        "jobs": jobs,
        "response_template": _response_template(batch_id),
    }


def build_batch_ai_review_json(session: Session, batch_id: str) -> bytes:
    from jolt.review_inbox_exchange import enrich_review_inbox_document

    document = enrich_review_inbox_document(
        build_batch_ai_review_document(session, batch_id)
    )
    return json.dumps(
        document,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")


def _validate_batch_membership(
    session: Session,
    request: BatchAIReviewImportRequest,
) -> dict[str, LinkedInDiscoveryBatchReviewItem]:
    items = list(
        session.scalars(
            select(LinkedInDiscoveryBatchReviewItem)
            .where(LinkedInDiscoveryBatchReviewItem.batch_id == request.discovery_batch_id)
            .order_by(LinkedInDiscoveryBatchReviewItem.position.asc())
        ).all()
    )
    if not items:
        raise ValueError(
            "Discovery batch review set has not been materialized; export it before import."
        )

    expected = {item.posting_id: item for item in items}
    seen: set[str] = set()
    for job in request.jobs:
        if job.posting_id in seen:
            raise ValueError(f"Duplicate posting_id in batch AI review: {job.posting_id}")
        seen.add(job.posting_id)

        expected_item = expected.get(job.posting_id)
        if expected_item is None:
            raise ValueError(
                f"AI review posting does not belong to the batch review set: {job.posting_id}"
            )
        if job.source_job_id != expected_item.representative_source_job_id:
            raise ValueError(
                f"AI review source_job_id does not match batch evidence for {job.posting_id}"
            )

        posting = session.get(Posting, job.posting_id)
        if posting is None:
            raise ValueError(f"AI review references unknown posting: {job.posting_id}")
        source_document = session.get(SourceDocument, posting.source_document_id)
        source_text = (
            source_document.raw_text if source_document is not None else posting.description
        )
        deterministic_location = analyze_location_evidence(
            location=posting.location,
            source_text=source_text,
        )
        if deterministic_location.hardline_reject and (
            job.hardline_status != "REJECT"
            or job.location_eligibility != "ineligible"
            or job.final_decision != "reject"
            or job.fit_analysis_allowed
            or job.technical_fit_percent is not None
        ):
            evidence = "; ".join(deterministic_location.negative_evidence)
            raise ValueError(
                "AI review conflicts with deterministic source evidence for "
                f"{job.posting_id}: {evidence}"
            )

        if job.duplicate_of_posting_id is not None:
            if job.duplicate_of_posting_id == job.posting_id:
                raise ValueError("A posting cannot be marked as a duplicate of itself.")
            if session.get(Posting, job.duplicate_of_posting_id) is None:
                raise ValueError(
                    "duplicate_of_posting_id references unknown posting: "
                    f"{job.duplicate_of_posting_id}"
                )

    expected_ids = set(expected)
    if seen != expected_ids:
        missing = sorted(expected_ids - seen)
        unexpected = sorted(seen - expected_ids)
        details = []
        if missing:
            details.append("missing posting_id(s): " + ", ".join(missing))
        if unexpected:
            details.append("unexpected posting_id(s): " + ", ".join(unexpected))
        raise ValueError(
            "Batch AI review must return exactly one result for every posting in the frozen review set; "
            + "; ".join(details)
        )
    return expected


def _requirement_json(items: list[MandatoryRequirementResult]) -> str:
    return json.dumps(
        [item.model_dump() for item in items],
        ensure_ascii=False,
    )


def import_batch_ai_review(
    session: Session,
    request: BatchAIReviewImportRequest,
) -> BatchAIReviewImportResponse:
    expected = _validate_batch_membership(session, request)
    posting_ids = [job.posting_id for job in request.jobs]

    protected_human_state = set(
        session.scalars(
            select(ReviewDecision.posting_id).where(ReviewDecision.posting_id.in_(posting_ids))
        ).all()
    ) | set(
        session.scalars(
            select(Application.posting_id).where(Application.posting_id.in_(posting_ids))
        ).all()
    )

    existing_reviews = {
        (review.capture_run_id, review.posting_id): review
        for review in session.scalars(
            select(AIReview).where(
                AIReview.review_source == request.review_source,
                AIReview.posting_id.in_(posting_ids),
            )
        ).all()
    }

    created_count = 0
    updated_count = 0
    imported_at = utc_now()

    for job in request.jobs:
        review_item = expected[job.posting_id]
        key = (review_item.representative_capture_run_id, job.posting_id)
        review = existing_reviews.get(key)
        values = {
            "source_job_id": job.source_job_id,
            "review_version": request.review_version,
            "contract_version": request.ai_review_contract_version,
            "decision": job.final_decision or job.decision,
            "priority_score": job.priority_score,
            "geography_status": job.geography_status,
            "clearance_status": job.clearance_status,
            "language_status": job.language_status,
            "technical_fit": job.technical_fit_percent,
            "hardline_status": job.hardline_status,
            "hardline_reasons_json": json.dumps(job.hardline_reasons, ensure_ascii=False),
            "location_eligibility": job.location_eligibility,
            "location_evidence_json": json.dumps(job.location_evidence, ensure_ascii=False),
            "mandatory_requirements_json": _requirement_json(job.mandatory_requirements),
            "mandatory_requirement_results_json": _requirement_json(
                job.mandatory_requirement_results
            ),
            "employment_constraints_json": json.dumps(
                job.employment_constraints, ensure_ascii=False
            ),
            "fit_analysis_allowed": job.fit_analysis_allowed,
            "decision_reason": job.decision_reason,
            "duplicate_of_posting_id": job.duplicate_of_posting_id,
            "summary": job.summary,
            "reasons_json": json.dumps(job.reasons, ensure_ascii=False),
            "reviewed_at": request.reviewed_at,
            "imported_at": imported_at,
        }

        if review is None:
            session.add(
                AIReview(
                    id=str(uuid4()),
                    capture_run_id=review_item.representative_capture_run_id,
                    posting_id=job.posting_id,
                    review_source=request.review_source,
                    **values,
                )
            )
            created_count += 1
        else:
            for field_name, value in values.items():
                setattr(review, field_name, value)
            updated_count += 1

    session.commit()
    return BatchAIReviewImportResponse(
        discovery_batch_id=request.discovery_batch_id,
        received_count=len(request.jobs),
        created_count=created_count,
        updated_count=updated_count,
        protected_human_state_count=len(protected_human_state),
    )
