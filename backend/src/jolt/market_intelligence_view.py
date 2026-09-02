from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeFeedbackItem
from jolt.ai_exchange_feedback_store import list_ai_exchange_feedback
from jolt.database import CaptureRun, MarketIntelligenceObservation
from jolt.global_context import global_context_version, load_global_ai_context


class MarketEvidenceProvenance(BaseModel):
    observation_count: int = 0
    canonical_role_count: int = 0
    duplicate_observation_count: int = 0
    capture_run_count: int = 0
    oldest_evidence_at: datetime | None = None
    newest_evidence_at: datetime | None = None
    latest_capture_at: datetime | None = None


class MarketFreshness(BaseModel):
    status: str
    ai_updated_at: datetime | None = None
    latest_capture_at: datetime | None = None
    needs_analysis: bool
    reason: str


class MarketIntelligenceView(BaseModel):
    authority: str = "chatgpt"
    context_version: str
    market_summary: dict[str, Any] = Field(default_factory=dict)
    skills_gap_summary: dict[str, Any] = Field(default_factory=dict)
    capture_strategy: dict[str, Any] = Field(default_factory=dict)
    application_strategy: dict[str, Any] = Field(default_factory=dict)
    profile_strategy: dict[str, Any] = Field(default_factory=dict)
    evidence_provenance: MarketEvidenceProvenance
    freshness: MarketFreshness
    latest_feedback: list[AIExchangeFeedbackItem] = Field(default_factory=list)
    recommendations: list[AIExchangeFeedbackItem] = Field(default_factory=list)


def _latest_capture_at(session: Session) -> datetime | None:
    runs = session.scalars(
        select(CaptureRun)
        .where(CaptureRun.status != "running")
        .order_by(CaptureRun.started_at.desc(), CaptureRun.id.desc())
        .limit(1)
    ).all()
    if not runs:
        return None
    run = runs[0]
    return run.completed_at or run.started_at


def _provenance(session: Session) -> MarketEvidenceProvenance:
    observation_count = int(
        session.scalar(select(func.count(MarketIntelligenceObservation.id))) or 0
    )
    canonical_role_count = int(
        session.scalar(
            select(func.count(func.distinct(MarketIntelligenceObservation.posting_identity_key)))
        )
        or 0
    )
    capture_run_count = int(
        session.scalar(
            select(func.count(func.distinct(MarketIntelligenceObservation.source_capture_run_id)))
        )
        or 0
    )
    oldest_evidence_at = session.scalar(select(func.min(MarketIntelligenceObservation.captured_at)))
    newest_evidence_at = session.scalar(select(func.max(MarketIntelligenceObservation.captured_at)))
    return MarketEvidenceProvenance(
        observation_count=observation_count,
        canonical_role_count=canonical_role_count,
        duplicate_observation_count=max(0, observation_count - canonical_role_count),
        capture_run_count=capture_run_count,
        oldest_evidence_at=oldest_evidence_at,
        newest_evidence_at=newest_evidence_at,
        latest_capture_at=_latest_capture_at(session),
    )


def _freshness(
    *,
    ai_updated_at: datetime | None,
    latest_capture_at: datetime | None,
    has_market_summary: bool,
) -> MarketFreshness:
    if not has_market_summary:
        return MarketFreshness(
            status="not_analyzed",
            ai_updated_at=ai_updated_at,
            latest_capture_at=latest_capture_at,
            needs_analysis=True,
            reason="No ChatGPT-derived market summary is stored yet.",
        )
    if latest_capture_at is not None and (
        ai_updated_at is None or latest_capture_at.astimezone(UTC) > ai_updated_at.astimezone(UTC)
    ):
        return MarketFreshness(
            status="stale",
            ai_updated_at=ai_updated_at,
            latest_capture_at=latest_capture_at,
            needs_analysis=True,
            reason="New captured market evidence is newer than the latest ChatGPT analysis.",
        )
    return MarketFreshness(
        status="current",
        ai_updated_at=ai_updated_at,
        latest_capture_at=latest_capture_at,
        needs_analysis=False,
        reason="Stored ChatGPT market intelligence covers the latest retained capture evidence.",
    )


def build_market_intelligence_view(session: Session) -> MarketIntelligenceView:
    context = load_global_ai_context()
    provenance = _provenance(session)
    feedback_index = list_ai_exchange_feedback("market_insights")
    latest_record = feedback_index.records[0] if feedback_index.records else None
    latest_feedback = latest_record.feedback if latest_record else []
    recommendations = [item for item in latest_feedback if item.feedback_type == "recommendation"]
    return MarketIntelligenceView(
        context_version=global_context_version(),
        market_summary=context.market_summary,
        skills_gap_summary=context.skills_gap_summary,
        capture_strategy=context.capture_strategy,
        application_strategy=context.application_strategy,
        profile_strategy=context.profile_strategy,
        evidence_provenance=provenance,
        freshness=_freshness(
            ai_updated_at=context.updated_at,
            latest_capture_at=provenance.latest_capture_at,
            has_market_summary=bool(context.market_summary),
        ),
        latest_feedback=latest_feedback,
        recommendations=recommendations,
    )
