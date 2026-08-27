from __future__ import annotations

import json
from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import (
    AIReview,
    Application,
    CaptureItem,
    CaptureRun,
    Posting,
    ReviewDecision,
    utc_now,
)
from jolt.errors import JoltNotFoundError

AIReviewDecision = Literal[
    "strong_pursue",
    "pursue",
    "conditional",
    "reject",
]

GeographyStatus = Literal[
    "eligible",
    "conditional",
    "ineligible",
    "unknown",
]

ClearanceStatus = Literal[
    "clear",
    "conditional",
    "blocked",
    "unknown",
]

LanguageStatus = Literal[
    "clear",
    "conditional",
    "blocked",
    "unknown",
]


class AIReviewJob(BaseModel):
    posting_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    decision: AIReviewDecision
    priority_score: int = Field(ge=0, le=100)
    geography_status: GeographyStatus
    clearance_status: ClearanceStatus
    language_status: LanguageStatus
    technical_fit: int = Field(ge=0, le=100)
    duplicate_of_posting_id: str | None = None
    summary: str = ""
    reasons: list[str] = Field(default_factory=list)


class AIReviewImportRequest(BaseModel):
    contract_type: Literal["jolt_ai_review"]
    contract_version: Literal["1.0"]
    capture_run_id: str = Field(min_length=1)
    review_source: Literal["chatgpt_source_first"]
    review_version: str = Field(min_length=1, max_length=80)
    reviewed_at: datetime
    jobs: list[AIReviewJob]


class AIReviewImportResponse(BaseModel):
    capture_run_id: str
    received_count: int
    created_count: int
    updated_count: int
    protected_human_state_count: int


def _validate_capture_membership(
    session: Session,
    request: AIReviewImportRequest,
) -> None:
    capture = session.get(CaptureRun, request.capture_run_id)
    if capture is None:
        raise JoltNotFoundError(f"Capture run not found: {request.capture_run_id}")

    capture_items = list(
        session.scalars(
            select(CaptureItem).where(CaptureItem.capture_run_id == request.capture_run_id)
        ).all()
    )

    source_job_by_posting = {
        item.posting_id: item.source_job_id for item in capture_items if item.posting_id is not None
    }

    seen_postings: set[str] = set()

    for job in request.jobs:
        if job.posting_id in seen_postings:
            raise ValueError(f"Duplicate posting_id in AI review payload: {job.posting_id}")

        seen_postings.add(job.posting_id)

        expected_source_job_id = source_job_by_posting.get(job.posting_id)

        if expected_source_job_id is None:
            raise ValueError(
                f"AI review posting does not belong to the stated capture: {job.posting_id}"
            )

        if expected_source_job_id != job.source_job_id:
            raise ValueError(
                f"AI review source_job_id does not match capture evidence for {job.posting_id}"
            )

        if session.get(Posting, job.posting_id) is None:
            raise ValueError(f"AI review references unknown posting: {job.posting_id}")

        if job.duplicate_of_posting_id is not None:
            if job.duplicate_of_posting_id == job.posting_id:
                raise ValueError("A posting cannot be marked as a duplicate of itself.")

            if (
                session.get(
                    Posting,
                    job.duplicate_of_posting_id,
                )
                is None
            ):
                raise ValueError(
                    "duplicate_of_posting_id references unknown posting: "
                    f"{job.duplicate_of_posting_id}"
                )


def import_ai_review(
    session: Session,
    request: AIReviewImportRequest,
) -> AIReviewImportResponse:
    """Persist external AI analysis without altering human/application state."""

    _validate_capture_membership(session, request)

    posting_ids = [job.posting_id for job in request.jobs]

    human_review_postings = set(
        session.scalars(
            select(ReviewDecision.posting_id).where(ReviewDecision.posting_id.in_(posting_ids))
        ).all()
    )

    application_postings = set(
        session.scalars(
            select(Application.posting_id).where(Application.posting_id.in_(posting_ids))
        ).all()
    )

    protected_human_state = human_review_postings | application_postings

    existing_reviews = {
        review.posting_id: review
        for review in session.scalars(
            select(AIReview).where(
                AIReview.capture_run_id == request.capture_run_id,
                AIReview.review_source == request.review_source,
                AIReview.posting_id.in_(posting_ids),
            )
        ).all()
    }

    created_count = 0
    updated_count = 0
    imported_at = utc_now()

    for job in request.jobs:
        review = existing_reviews.get(job.posting_id)

        if review is None:
            review = AIReview(
                id=str(uuid4()),
                capture_run_id=request.capture_run_id,
                posting_id=job.posting_id,
                source_job_id=job.source_job_id,
                review_source=request.review_source,
                review_version=request.review_version,
                contract_version=request.contract_version,
                decision=job.decision,
                priority_score=job.priority_score,
                geography_status=job.geography_status,
                clearance_status=job.clearance_status,
                language_status=job.language_status,
                technical_fit=job.technical_fit,
                duplicate_of_posting_id=job.duplicate_of_posting_id,
                summary=job.summary,
                reasons_json=json.dumps(
                    job.reasons,
                    ensure_ascii=False,
                ),
                reviewed_at=request.reviewed_at,
                imported_at=imported_at,
            )
            session.add(review)
            created_count += 1
            continue

        review.source_job_id = job.source_job_id
        review.review_version = request.review_version
        review.contract_version = request.contract_version
        review.decision = job.decision
        review.priority_score = job.priority_score
        review.geography_status = job.geography_status
        review.clearance_status = job.clearance_status
        review.language_status = job.language_status
        review.technical_fit = job.technical_fit
        review.duplicate_of_posting_id = job.duplicate_of_posting_id
        review.summary = job.summary
        review.reasons_json = json.dumps(
            job.reasons,
            ensure_ascii=False,
        )
        review.reviewed_at = request.reviewed_at
        review.imported_at = imported_at
        updated_count += 1

    session.commit()

    return AIReviewImportResponse(
        capture_run_id=request.capture_run_id,
        received_count=len(request.jobs),
        created_count=created_count,
        updated_count=updated_count,
        protected_human_state_count=len(protected_human_state),
    )
