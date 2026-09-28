from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import (
    AIReview,
    Application,
    ApplicationEvent,
    CaptureItem,
    LinkedInDiscoveryBatchSearch,
    LinkedInSavedSearch,
    Outcome,
    ReviewDecision,
)


class LinkedInSearchPerformanceItem(BaseModel):
    saved_search_id: str
    label: str
    enabled: bool
    completed_runs: int
    captured_count: int
    verified_count: int
    new_posting_count: int
    duplicate_count: int
    canonical_posting_count: int
    ai_reviewed_count: int
    ai_strong_pursue_count: int
    ai_pursue_count: int
    ai_conditional_count: int
    ai_actionable_count: int
    human_pursue_count: int
    application_count: int
    applied_count: int
    interview_count: int
    offer_count: int
    accepted_offer_count: int


_APPLIED_STAGES = {
    "submitted",
    "acknowledged",
    "recruiter_screen",
    "technical_interview",
    "hiring_manager_interview",
    "final_interview",
    "offer",
}
_INTERVIEW_STAGES = {
    "recruiter_screen",
    "technical_interview",
    "hiring_manager_interview",
    "final_interview",
}


def _latest_ai_reviews(session: Session, posting_ids: set[str]) -> dict[str, AIReview]:
    if not posting_ids:
        return {}
    rows = session.scalars(
        select(AIReview)
        .where(AIReview.posting_id.in_(posting_ids))
        .order_by(AIReview.posting_id.asc(), AIReview.imported_at.desc())
    ).all()
    latest: dict[str, AIReview] = {}
    for row in rows:
        latest.setdefault(row.posting_id, row)
    return latest


def _latest_human_reviews(
    session: Session,
    posting_ids: set[str],
) -> dict[str, ReviewDecision]:
    if not posting_ids:
        return {}
    rows = session.scalars(
        select(ReviewDecision)
        .where(ReviewDecision.posting_id.in_(posting_ids))
        .order_by(ReviewDecision.posting_id.asc(), ReviewDecision.reviewed_at.desc())
    ).all()
    latest: dict[str, ReviewDecision] = {}
    for row in rows:
        latest.setdefault(row.posting_id, row)
    return latest


def build_linkedin_search_performance(
    session: Session,
) -> list[LinkedInSearchPerformanceItem]:
    searches = list(
        session.scalars(
            select(LinkedInSavedSearch).order_by(
                LinkedInSavedSearch.enabled.desc(),
                LinkedInSavedSearch.label.asc(),
            )
        ).all()
    )
    results: list[LinkedInSearchPerformanceItem] = []

    for saved_search in searches:
        runs = list(
            session.scalars(
                select(LinkedInDiscoveryBatchSearch).where(
                    LinkedInDiscoveryBatchSearch.saved_search_id == saved_search.id
                )
            ).all()
        )
        capture_run_ids = {
            run.capture_run_id
            for run in runs
            if run.capture_run_id is not None
        }

        posting_ids: set[str] = set()
        if capture_run_ids:
            posting_ids = {
                posting_id
                for posting_id in session.scalars(
                    select(CaptureItem.posting_id).where(
                        CaptureItem.capture_run_id.in_(capture_run_ids),
                        CaptureItem.posting_id.is_not(None),
                    )
                ).all()
                if posting_id is not None
            }

        ai_reviews = _latest_ai_reviews(session, posting_ids)
        human_reviews = _latest_human_reviews(session, posting_ids)

        applications = list(
            session.scalars(
                select(Application).where(Application.posting_id.in_(posting_ids))
            ).all()
        ) if posting_ids else []
        applications_by_id = {application.id: application for application in applications}
        application_ids = set(applications_by_id)

        reached_stages: dict[str, set[str]] = {
            application_id: set() for application_id in application_ids
        }
        if application_ids:
            events = session.scalars(
                select(ApplicationEvent).where(
                    ApplicationEvent.application_id.in_(application_ids)
                )
            ).all()
            for event in events:
                reached_stages.setdefault(event.application_id, set()).add(event.to_status)

        outcomes = list(
            session.scalars(
                select(Outcome).where(Outcome.application_id.in_(application_ids))
            ).all()
        ) if application_ids else []
        outcomes_by_application = {
            outcome.application_id: outcome
            for outcome in outcomes
            if outcome.application_id is not None
        }

        applied_count = 0
        interview_count = 0
        offer_count = 0
        accepted_offer_count = 0

        for application in applications:
            stages = reached_stages.get(application.id, set())
            outcome = outcomes_by_application.get(application.id)
            if stages & _APPLIED_STAGES:
                applied_count += 1
            if stages & _INTERVIEW_STAGES:
                interview_count += 1
            if "offer" in stages:
                offer_count += 1
            if outcome is not None and outcome.outcome_type == "offer_accepted":
                accepted_offer_count += 1

        ai_strong = sum(
            1 for review in ai_reviews.values() if review.decision == "strong_pursue"
        )
        ai_pursue = sum(
            1 for review in ai_reviews.values() if review.decision == "pursue"
        )
        ai_conditional = sum(
            1 for review in ai_reviews.values() if review.decision == "conditional"
        )

        results.append(
            LinkedInSearchPerformanceItem(
                saved_search_id=saved_search.id,
                label=saved_search.label,
                enabled=saved_search.enabled,
                completed_runs=sum(1 for run in runs if run.status == "completed"),
                captured_count=sum(run.captured_count for run in runs),
                verified_count=sum(run.verified_count for run in runs),
                new_posting_count=sum(run.new_posting_count for run in runs),
                duplicate_count=sum(run.duplicate_count for run in runs),
                canonical_posting_count=len(posting_ids),
                ai_reviewed_count=len(ai_reviews),
                ai_strong_pursue_count=ai_strong,
                ai_pursue_count=ai_pursue,
                ai_conditional_count=ai_conditional,
                ai_actionable_count=ai_strong + ai_pursue + ai_conditional,
                human_pursue_count=sum(
                    1 for review in human_reviews.values() if review.decision == "pursue"
                ),
                application_count=len(applications),
                applied_count=applied_count,
                interview_count=interview_count,
                offer_count=offer_count,
                accepted_offer_count=accepted_offer_count,
            )
        )

    return results
