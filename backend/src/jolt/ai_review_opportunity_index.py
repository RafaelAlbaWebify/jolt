from __future__ import annotations

import json

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.application_archival import ARCHIVED_APPLICATION_STATUS
from jolt.capture_archival import ARCHIVED_CAPTURE_STATUS
from jolt.database import (
    AIReview,
    Application,
    CaptureItem,
    CaptureRun,
    Posting,
    ReviewDecision,
    SourceDocument,
)
from jolt.linkedin_source_urls import absolute_linkedin_url


class AIReviewOpportunityIndexItem(BaseModel):
    posting_id: str
    source_url: str
    title: str
    company: str
    location: str

    ai_review_id: str | None = None
    ai_review_status: str

    decision: str | None = None
    priority_score: int | None = None

    hardline_status: str | None = None
    hardline_reasons: list[str] = Field(default_factory=list)
    location_eligibility: str | None = None
    location_evidence: list[str] = Field(default_factory=list)
    mandatory_requirements: list[dict[str, object]] = Field(default_factory=list)
    mandatory_requirement_results: list[dict[str, object]] = Field(default_factory=list)
    employment_constraints: list[str] = Field(default_factory=list)
    fit_analysis_allowed: bool | None = None
    decision_reason: str = ""

    geography_status: str | None = None
    clearance_status: str | None = None
    language_status: str | None = None
    technical_fit: int | None = None

    duplicate_of_posting_id: str | None = None

    summary: str = ""
    reasons: list[str] = Field(default_factory=list)

    review_decision: str | None = None
    application_id: str | None = None
    application_status: str | None = None

    reviewed_at: str | None = None
    imported_at: str | None = None


_CAPTURE_SOURCE_TYPES = {
    "linkedin_fixture",
    "linkedin_live",
}


_DECISION_PRIORITY = {
    "strong_pursue": 0,
    "pursue": 1,
    "conditional": 2,
    "awaiting_ai_review": 3,
    "reject": 4,
}


def _display_source_url(
    source_document: SourceDocument | None,
    canonical_url: str,
) -> str:
    source_url = source_document.source_url if source_document is not None else canonical_url

    if source_url.startswith(
        (
            "/jobs/",
            "jobs/",
            "//www.linkedin.com/",
        )
    ):
        return absolute_linkedin_url(source_url)

    if source_document is not None and source_document.source_type in _CAPTURE_SOURCE_TYPES:
        return absolute_linkedin_url(source_url)

    return source_url


def _capture_statuses_by_posting(
    session: Session,
) -> dict[str, set[str]]:
    runs = {run.id: run for run in session.scalars(select(CaptureRun)).all()}

    statuses: dict[str, set[str]] = {}

    for item in session.scalars(
        select(CaptureItem).where(CaptureItem.posting_id.is_not(None))
    ).all():
        if item.posting_id is None:
            continue

        run = runs.get(item.capture_run_id)

        if run is None:
            continue

        statuses.setdefault(
            item.posting_id,
            set(),
        ).add(run.status)

    return statuses


def _latest_ai_reviews(
    session: Session,
) -> dict[str, AIReview]:
    latest: dict[str, AIReview] = {}

    reviews = session.scalars(
        select(AIReview).order_by(
            AIReview.imported_at.desc(),
            AIReview.reviewed_at.desc(),
            AIReview.id.desc(),
        )
    ).all()

    for review in reviews:
        latest.setdefault(
            review.posting_id,
            review,
        )

    return latest


def _json_list(value: str) -> list[object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _string_list(value: str) -> list[str]:
    return [str(item) for item in _json_list(value)]


def _object_list(value: str) -> list[dict[str, object]]:
    return [item for item in _json_list(value) if isinstance(item, dict)]


def _sort_key(
    item: AIReviewOpportunityIndexItem,
) -> tuple[int, int, str]:
    effective_decision = (
        item.decision if item.ai_review_status == "reviewed" else "awaiting_ai_review"
    )

    score = item.priority_score if item.priority_score is not None else -1

    return (
        _DECISION_PRIORITY.get(
            effective_decision or "",
            3,
        ),
        -score,
        item.title.casefold(),
    )


def list_ai_review_opportunity_index(
    session: Session,
) -> list[AIReviewOpportunityIndexItem]:
    """Return Review Inbox state using AI reviews as the only classifier authority.

    Python Evaluation records are deliberately not queried here.
    """

    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()

    source_documents = {
        source.id: source for source in session.scalars(select(SourceDocument)).all()
    }

    latest_ai_reviews = _latest_ai_reviews(session)

    latest_human_reviews: dict[str, ReviewDecision] = {}

    for review in session.scalars(
        select(ReviewDecision).order_by(ReviewDecision.reviewed_at.desc())
    ).all():
        latest_human_reviews.setdefault(
            review.posting_id,
            review,
        )

    applications = {
        application.posting_id: application
        for application in session.scalars(select(Application)).all()
    }

    capture_statuses = _capture_statuses_by_posting(session)

    results: list[AIReviewOpportunityIndexItem] = []

    for posting in postings:
        application = applications.get(posting.id)

        if application is not None:
            if application.status != ARCHIVED_APPLICATION_STATUS:
                continue
            continue

        if posting.id in latest_human_reviews:
            continue

        statuses = capture_statuses.get(
            posting.id,
            set(),
        )

        if statuses and all(status == ARCHIVED_CAPTURE_STATUS for status in statuses):
            continue

        source_document = source_documents.get(posting.source_document_id)

        if (
            not statuses
            and source_document is not None
            and source_document.source_type in _CAPTURE_SOURCE_TYPES
        ):
            continue

        ai_review = latest_ai_reviews.get(posting.id)

        if ai_review is None:
            results.append(
                AIReviewOpportunityIndexItem(
                    posting_id=posting.id,
                    source_url=_display_source_url(
                        source_document,
                        posting.canonical_url,
                    ),
                    title=posting.title,
                    company=posting.company,
                    location=posting.location,
                    ai_review_status="awaiting_ai_review",
                )
            )
            continue

        results.append(
            AIReviewOpportunityIndexItem(
                posting_id=posting.id,
                source_url=_display_source_url(
                    source_document,
                    posting.canonical_url,
                ),
                title=posting.title,
                company=posting.company,
                location=posting.location,
                ai_review_id=ai_review.id,
                ai_review_status="reviewed",
                decision=ai_review.decision,
                priority_score=ai_review.priority_score,
                hardline_status=ai_review.hardline_status,
                hardline_reasons=_string_list(ai_review.hardline_reasons_json),
                location_eligibility=ai_review.location_eligibility,
                location_evidence=_string_list(ai_review.location_evidence_json),
                mandatory_requirements=_object_list(ai_review.mandatory_requirements_json),
                mandatory_requirement_results=_object_list(
                    ai_review.mandatory_requirement_results_json
                ),
                employment_constraints=_string_list(ai_review.employment_constraints_json),
                fit_analysis_allowed=ai_review.fit_analysis_allowed,
                decision_reason=ai_review.decision_reason,
                geography_status=ai_review.geography_status,
                clearance_status=ai_review.clearance_status,
                language_status=ai_review.language_status,
                technical_fit=ai_review.technical_fit,
                duplicate_of_posting_id=ai_review.duplicate_of_posting_id,
                summary=ai_review.summary,
                reasons=_string_list(ai_review.reasons_json),
                reviewed_at=ai_review.reviewed_at.isoformat(),
                imported_at=ai_review.imported_at.isoformat(),
            )
        )

    results.sort(key=_sort_key)

    return results
