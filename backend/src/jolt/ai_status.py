from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jolt.ai_exchange_feedback_store import AIExchangeFeedbackRecord, list_ai_exchange_feedback
from jolt.ai_review_opportunity_index import list_ai_review_opportunity_index
from jolt.database import (
    AIReview,
    Application,
    ApplicationEvent,
    CaptureRun,
    LinkedInDiscoveryBatch,
    LinkedInPresenceCapture,
    Outcome,
    Posting,
)
from jolt.global_context import load_global_ai_context
from jolt.market_intelligence_view import build_market_intelligence_view

AISectionState = Literal["no_evidence", "not_analyzed", "stale", "current"]
AIOverallState = Literal["no_evidence", "update_available", "current"]


class AISectionStatus(BaseModel):
    state: AISectionState
    evidence_at: datetime | None = None
    analyzed_at: datetime | None = None
    reason: str
    operator_relevant: bool = True


class AIStatusResponse(BaseModel):
    overall_status: AIOverallState
    last_intelligence_update_at: datetime | None = None
    context_updated_at: datetime | None = None
    current_sections: int = 0
    attention_sections: int = 0
    sections: dict[str, AISectionStatus] = Field(default_factory=dict)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _latest_feedback(section: str) -> AIExchangeFeedbackRecord | None:
    records = list_ai_exchange_feedback(section).records
    return records[0] if records else None


def _latest_capture_at(session: Session) -> datetime | None:
    run = session.scalar(
        select(CaptureRun)
        .where(CaptureRun.status != "running")
        .order_by(CaptureRun.started_at.desc(), CaptureRun.id.desc())
        .limit(1)
    )
    if run is None:
        return None
    return _as_utc(run.completed_at or run.started_at)


def _latest_application_evidence_at(session: Session) -> datetime | None:
    values = [
        session.scalar(select(func.max(Application.updated_at))),
        session.scalar(select(func.max(ApplicationEvent.occurred_at))),
        session.scalar(select(func.max(Outcome.recorded_at))),
    ]
    normalized: list[datetime] = []
    for value in values:
        converted = _as_utc(value)
        if converted is not None:
            normalized.append(converted)
    return max(normalized) if normalized else None


def _latest_search_evidence_at(session: Session) -> datetime | None:
    value = session.scalar(
        select(func.max(LinkedInDiscoveryBatch.completed_at)).where(
            LinkedInDiscoveryBatch.completed_at.is_not(None)
        )
    )
    return _as_utc(value)


def _latest_linkedin_evidence_at(session: Session) -> datetime | None:
    return _as_utc(session.scalar(select(func.max(LinkedInPresenceCapture.captured_at))))


def _latest_posting_evidence_at(session: Session) -> datetime | None:
    return _as_utc(session.scalar(select(func.max(Posting.created_at))))


def _feedback_status(
    *,
    evidence_at: datetime | None,
    feedback: AIExchangeFeedbackRecord | None,
    no_evidence_reason: str,
    not_analyzed_reason: str,
    stale_reason: str,
    current_reason: str,
    operator_relevant: bool = True,
) -> AISectionStatus:
    analyzed_at = _as_utc(feedback.reviewed_at) if feedback else None
    if evidence_at is None:
        return AISectionStatus(
            state="no_evidence",
            analyzed_at=analyzed_at,
            reason=no_evidence_reason,
            operator_relevant=operator_relevant,
        )
    if analyzed_at is None:
        return AISectionStatus(
            state="not_analyzed",
            evidence_at=evidence_at,
            reason=not_analyzed_reason,
            operator_relevant=operator_relevant,
        )
    if evidence_at > analyzed_at:
        return AISectionStatus(
            state="stale",
            evidence_at=evidence_at,
            analyzed_at=analyzed_at,
            reason=stale_reason,
            operator_relevant=operator_relevant,
        )
    return AISectionStatus(
        state="current",
        evidence_at=evidence_at,
        analyzed_at=analyzed_at,
        reason=current_reason,
        operator_relevant=operator_relevant,
    )


def _review_inbox_status(session: Session) -> AISectionStatus:
    pending = list_ai_review_opportunity_index(session)
    awaiting_count = sum(item.ai_review_status != "reviewed" for item in pending)
    analyzed_at = _as_utc(session.scalar(select(func.max(AIReview.reviewed_at))))
    evidence_at = _latest_capture_at(session)

    if evidence_at is None and not pending:
        return AISectionStatus(
            state="no_evidence",
            analyzed_at=analyzed_at,
            reason="No captured job evidence is waiting for AI review.",
        )
    if awaiting_count:
        return AISectionStatus(
            state="not_analyzed" if analyzed_at is None else "stale",
            evidence_at=evidence_at,
            analyzed_at=analyzed_at,
            reason=f"{awaiting_count} pending job{'s' if awaiting_count != 1 else ''} still need AI review.",
        )
    return AISectionStatus(
        state="current",
        evidence_at=evidence_at,
        analyzed_at=analyzed_at,
        reason="No pending Review Inbox job is waiting for AI analysis.",
    )


def build_ai_status(session: Session) -> AIStatusResponse:
    latest_capture_at = _latest_capture_at(session)
    latest_linkedin_at = _latest_linkedin_evidence_at(session)
    latest_application_at = _latest_application_evidence_at(session)
    latest_search_at = _latest_search_evidence_at(session)
    latest_posting_at = _latest_posting_evidence_at(session)

    market_view = build_market_intelligence_view(session)
    market_has_evidence = (
        market_view.evidence_provenance.observation_count > 0
        or market_view.evidence_provenance.latest_capture_at is not None
    )
    if not market_has_evidence:
        market_status = AISectionStatus(
            state="no_evidence",
            analyzed_at=_as_utc(market_view.freshness.ai_updated_at),
            reason="No retained market evidence is available yet.",
        )
    else:
        market_state = (
            market_view.freshness.status
            if market_view.freshness.status in {"not_analyzed", "stale", "current"}
            else "not_analyzed"
        )
        market_status = AISectionStatus(
            state=cast(AISectionState, market_state),
            evidence_at=_as_utc(market_view.freshness.latest_capture_at),
            analyzed_at=_as_utc(market_view.freshness.ai_updated_at),
            reason=market_view.freshness.reason,
        )

    sections = {
        "review_inbox": _review_inbox_status(session),
        "market_insights": market_status,
        "applications": _feedback_status(
            evidence_at=latest_application_at,
            feedback=_latest_feedback("applications"),
            no_evidence_reason="No Applications evidence exists yet.",
            not_analyzed_reason="Applications exist but no outcome/process analysis has been imported.",
            stale_reason="Application activity is newer than the latest Applications analysis.",
            current_reason="Applications analysis covers the latest recorded activity.",
        ),
        "linkedin_profile": _feedback_status(
            evidence_at=latest_linkedin_at,
            feedback=_latest_feedback("linkedin_profile"),
            no_evidence_reason="No LinkedIn profile evidence has been captured yet.",
            not_analyzed_reason="LinkedIn evidence exists but has not been analyzed.",
            stale_reason="LinkedIn evidence is newer than the latest profile analysis.",
            current_reason="LinkedIn analysis covers the latest profile evidence.",
        ),
        "search_strategy": _feedback_status(
            evidence_at=latest_search_at,
            feedback=_latest_feedback("search_preferences"),
            no_evidence_reason="No completed discovery batch exists yet.",
            not_analyzed_reason="Search history exists but search strategy has not been analyzed.",
            stale_reason="Search performance evidence is newer than the latest search-strategy analysis.",
            current_reason="Search strategy covers the latest completed discovery evidence.",
        ),
        "skills_gaps": _feedback_status(
            evidence_at=latest_capture_at,
            feedback=_latest_feedback("skills_gaps"),
            no_evidence_reason="No captured jobs are available for skills-gap analysis.",
            not_analyzed_reason="Job evidence exists but skills gaps have not been analyzed.",
            stale_reason="Job evidence is newer than the latest skills-gap analysis.",
            current_reason="Skills-gap analysis covers the latest captured evidence.",
        ),
        "professional_evidence": _feedback_status(
            evidence_at=latest_linkedin_at,
            feedback=_latest_feedback("professional_evidence"),
            no_evidence_reason="No professional-profile evidence is available yet.",
            not_analyzed_reason="Professional evidence exists but has not been analyzed.",
            stale_reason="Professional evidence is newer than the latest professional-evidence analysis.",
            current_reason="Professional-evidence analysis covers the latest retained evidence.",
        ),
        "data_quality": _feedback_status(
            evidence_at=max(
                [value for value in (latest_capture_at, latest_posting_at) if value is not None],
                default=None,
            ),
            feedback=_latest_feedback("data_quality"),
            no_evidence_reason="No captured or posting evidence exists for a data-quality review.",
            not_analyzed_reason="Data exists but no data-quality AI audit has been imported.",
            stale_reason="Stored data is newer than the latest data-quality AI audit.",
            current_reason="Data-quality analysis covers the latest retained data.",
            operator_relevant=False,
        ),
    }

    relevant = [status for status in sections.values() if status.operator_relevant]
    attention = [status for status in relevant if status.state in {"not_analyzed", "stale"}]
    current = [status for status in relevant if status.state == "current"]
    if attention:
        overall_status: AIOverallState = "update_available"
    elif any(status.state != "no_evidence" for status in relevant):
        overall_status = "current"
    else:
        overall_status = "no_evidence"

    feedback_records = list_ai_exchange_feedback().records
    imported_times = [_as_utc(record.imported_at) for record in feedback_records]
    ai_review_imported_at = _as_utc(session.scalar(select(func.max(AIReview.imported_at))))
    context = load_global_ai_context()
    candidates = [
        value
        for value in [
            *imported_times,
            ai_review_imported_at,
            _as_utc(context.updated_at),
        ]
        if value is not None
    ]

    return AIStatusResponse(
        overall_status=overall_status,
        last_intelligence_update_at=max(candidates) if candidates else None,
        context_updated_at=_as_utc(context.updated_at),
        current_sections=len(current),
        attention_sections=len(attention),
        sections=sections,
    )
