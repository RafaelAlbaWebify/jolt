from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from jolt.professional_intelligence_capture_runs import get_professional_capture_run
from jolt.professional_intelligence_sources import ProfessionalSourceCategory

RoutingBucket = Literal[
    "job_opportunity",
    "linkedin_presence",
    "market_signal",
    "unclassified_evidence",
    "rejected_noise",
]
RoutingStatus = Literal["pending", "in_progress", "routed", "needs_review", "rejected"]


class ProfessionalSourceRoutingDecision(BaseModel):
    source_id: str
    label: str
    source_category: str
    target_bucket: RoutingBucket
    target_workspace: str
    routing_status: RoutingStatus
    reason: str


class ProfessionalRoutingCounts(BaseModel):
    job_opportunities: int = 0
    linkedin_presence: int = 0
    market_signals: int = 0
    unclassified_evidence: int = 0
    rejected_noise: int = 0


class ProfessionalCaptureRoutingSummary(BaseModel):
    capture_run_id: str
    run_status: str
    artifact_count: int
    total_sources: int
    completed_sources: int
    counts: ProfessionalRoutingCounts
    decisions: list[ProfessionalSourceRoutingDecision] = Field(default_factory=list)
    explanation: str


def _progress_by_source(run) -> dict[str, object]:
    return {progress.source_id: progress for progress in run.source_progress}


def _routing_status(run_status: str, source_status: str, target_bucket: RoutingBucket) -> RoutingStatus:
    if source_status in {"failed", "skipped", "cancelled"}:
        return "rejected"
    if run_status == "running" or source_status == "running":
        return "in_progress"
    if source_status == "pending" or run_status in {"planned", "authorized", "expired"}:
        return "pending"
    if target_bucket == "market_signal":
        return "needs_review"
    return "routed"


def _classify_source(source, source_status: str) -> tuple[RoutingBucket, str, str]:
    if source_status in {"failed", "skipped", "cancelled"}:
        return (
            "rejected_noise",
            "Capture & Evidence",
            "The source did not complete cleanly, so it is retained as governed evidence and must not create job records.",
        )

    if source.category in {ProfessionalSourceCategory.PROFILE, ProfessionalSourceCategory.NETWORK}:
        return (
            "linkedin_presence",
            "LinkedIn Command Center",
            "Profile, activity, and network evidence belongs to LinkedIn positioning, not the Review Inbox.",
        )

    if source.category == ProfessionalSourceCategory.CAREER or "jobs" in source.source_id:
        return (
            "market_signal",
            "Market Insights / Evidence review",
            "Career/job-search pages are market evidence until individual verified job cards are ingested into the opportunity pipeline.",
        )

    return (
        "unclassified_evidence",
        "Evidence Inbox",
        "The source does not match a deterministic routing rule yet and needs manual review.",
    )


def build_professional_capture_routing_summary(
    session: Session, run_id: str
) -> ProfessionalCaptureRoutingSummary:
    run = get_professional_capture_run(session, run_id)
    progress_by_source = _progress_by_source(run)
    bucket_counts: Counter[str] = Counter()
    decisions: list[ProfessionalSourceRoutingDecision] = []

    for source in run.planned_sources:
        progress = progress_by_source.get(source.source_id)
        source_status = getattr(progress, "status", "pending") if progress else "pending"
        bucket, workspace, reason = _classify_source(source, source_status)
        bucket_counts[bucket] += 1
        decisions.append(
            ProfessionalSourceRoutingDecision(
                source_id=source.source_id,
                label=source.label,
                source_category=str(source.category),
                target_bucket=bucket,
                target_workspace=workspace,
                routing_status=_routing_status(run.status, source_status, bucket),
                reason=reason,
            )
        )

    counts = ProfessionalRoutingCounts(
        job_opportunities=bucket_counts["job_opportunity"],
        linkedin_presence=bucket_counts["linkedin_presence"],
        market_signals=bucket_counts["market_signal"],
        unclassified_evidence=bucket_counts["unclassified_evidence"],
        rejected_noise=bucket_counts["rejected_noise"],
    )
    return ProfessionalCaptureRoutingSummary(
        capture_run_id=run.id,
        run_status=run.status,
        artifact_count=run.artifact_count,
        total_sources=run.total_source_count,
        completed_sources=run.completed_source_count,
        counts=counts,
        decisions=decisions,
        explanation=(
            "This summary explains where captured evidence is allowed to go. "
            "Verified job-item capture uses the canonical opportunity pipeline. "
            "This supervised professional capture ledger stores source evidence and routes profile/network evidence to LinkedIn positioning, career pages to market/evidence review, and failed sources to rejected noise."
        ),
    )
