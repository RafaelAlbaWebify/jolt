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
from jolt.market_preparation_import import (
    MarketPreparationAction,
    MarketPreparationImportRequest,
    import_market_preparation,
)

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

GeographyBasis = Literal[
    "explicit_eligible",
    "neutral_location",
    "explicit_restricted",
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

Learnability = Literal[
    "already_ready",
    "quick_1_7_days",
    "short_1_2_weeks",
    "substantial",
    "unknown",
]

HardBlockerType = Literal[
    "language",
    "geography",
    "work_authorization",
    "citizenship",
    "clearance",
    "duplicate",
    "other_legal",
]


class AIReviewHardBlocker(BaseModel):
    blocker_type: HardBlockerType
    evidence: str = Field(min_length=1)


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

    # Contract v2 structured analysis. Defaults preserve v1 compatibility.
    geography_basis: GeographyBasis = "unknown"
    hard_blockers: list[AIReviewHardBlocker] = Field(default_factory=list)
    transferable_skills: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)
    learnability: Learnability = "unknown"
    preparation_actions: list[str] = Field(default_factory=list)
    language_required_level: str | None = None
    language_certificate_required: bool = False
    language_requirement_evidence: str | None = None


class AIMarketInsights(BaseModel):
    summary: str = ""
    demanded_technologies: list[str] = Field(default_factory=list)
    recurring_skill_gaps: list[str] = Field(default_factory=list)
    quick_learn_gaps: list[str] = Field(default_factory=list)
    strong_existing_skills: list[str] = Field(default_factory=list)
    promising_role_families: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)
    learning_priorities: list[str] = Field(default_factory=list)
    application_strategy: list[str] = Field(default_factory=list)


class AIReviewImportRequest(BaseModel):
    contract_type: Literal["jolt_ai_review"]
    contract_version: Literal["1.0", "2.0"]
    capture_run_id: str = Field(min_length=1)
    review_source: Literal["chatgpt_source_first"]
    review_version: str = Field(min_length=1, max_length=80)
    reviewed_at: datetime
    jobs: list[AIReviewJob]
    market_insights: AIMarketInsights | None = None


class AIReviewImportResponse(BaseModel):
    capture_run_id: str
    received_count: int
    created_count: int
    updated_count: int
    protected_human_state_count: int
    market_insight_action_count: int = 0


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

            if session.get(Posting, job.duplicate_of_posting_id) is None:
                raise ValueError(
                    "duplicate_of_posting_id references unknown posting: "
                    f"{job.duplicate_of_posting_id}"
                )


def _analysis_payload(job: AIReviewJob) -> dict[str, object]:
    return {
        "reasons": job.reasons,
        "geography_basis": job.geography_basis,
        "hard_blockers": [item.model_dump(mode="json") for item in job.hard_blockers],
        "transferable_skills": job.transferable_skills,
        "skill_gaps": job.skill_gaps,
        "learnability": job.learnability,
        "preparation_actions": job.preparation_actions,
        "language_required_level": job.language_required_level,
        "language_certificate_required": job.language_certificate_required,
        "language_requirement_evidence": job.language_requirement_evidence,
    }


def _market_actions(
    market: AIMarketInsights,
) -> MarketPreparationImportRequest:
    def actions(
        values: list[str],
        *,
        action_type: str,
        rationale: str,
        priority: Literal["high", "medium", "low"] = "medium",
    ) -> list[MarketPreparationAction]:
        return [
            MarketPreparationAction(
                action_type=action_type,
                title=value,
                rationale=rationale,
                proposed_action=value,
                priority=priority,
                source="chatgpt_ai_review_v2",
            )
            for value in values
        ]

    return MarketPreparationImportRequest(
        source="chatgpt_ai_review_v2",
        summary=market.summary,
        market_recommendations=(
            actions(
                market.demanded_technologies,
                action_type="market_demand",
                rationale="Technology demand observed across the reviewed vacancy batch.",
            )
            + actions(
                market.promising_role_families,
                action_type="role_family",
                rationale="Role family with useful transferability or market demand.",
            )
        ),
        preparation_plan=(
            actions(
                market.quick_learn_gaps,
                action_type="quick_learning",
                rationale="Gap judged practical to close quickly with focused study or lab work.",
                priority="high",
            )
            + actions(
                market.learning_priorities,
                action_type="learning_priority",
                rationale="Learning priority derived from the reviewed vacancy batch.",
                priority="high",
            )
            + actions(
                market.recurring_skill_gaps,
                action_type="recurring_gap",
                rationale="Recurring skill gap found across multiple opportunities.",
            )
        ),
        search_filter_improvements=actions(
            market.search_terms,
            action_type="search_term",
            rationale="Search term suggested by current market evidence.",
        ),
        application_strategy=actions(
            market.application_strategy,
            action_type="application_strategy",
            rationale="Application strategy derived from the same AI review round.",
        ),
        raw_payload=market.model_dump(mode="json"),
    )


def import_ai_review(
    session: Session,
    request: AIReviewImportRequest,
) -> AIReviewImportResponse:
    """Persist external AI analysis without altering human/application state.

    Contract v2 also imports market and preparation intelligence from the same
    review round, eliminating the need for a second ChatGPT interchange package.
    """

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
        analysis_json = json.dumps(
            _analysis_payload(job),
            ensure_ascii=False,
            sort_keys=True,
        )
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
                reasons_json=analysis_json,
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
        review.reasons_json = analysis_json
        review.reviewed_at = request.reviewed_at
        review.imported_at = imported_at
        updated_count += 1

    session.commit()

    market_action_count = 0
    if request.market_insights is not None:
        market_response = import_market_preparation(_market_actions(request.market_insights))
        market_action_count = market_response.imported_count

    return AIReviewImportResponse(
        capture_run_id=request.capture_run_id,
        received_count=len(request.jobs),
        created_count=created_count,
        updated_count=updated_count,
        protected_human_state_count=len(protected_human_state),
        market_insight_action_count=market_action_count,
    )
