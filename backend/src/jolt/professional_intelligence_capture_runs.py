from __future__ import annotations

import json
from datetime import datetime, timedelta
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jolt.database import utc_now
from jolt.errors import JoltNotFoundError
from jolt.professional_intelligence_capture_plan import build_professional_capture_plan
from jolt.professional_intelligence_records import (
    ProfessionalCaptureArtifact,
    ProfessionalCaptureRun,
)
from jolt.professional_intelligence_sources import ProfessionalIntelligenceSource

AUTHORIZATION_CONFIRMATION_PHRASE = "I UNDERSTAND THIS WILL OPEN LINKEDIN"
AUTHORIZATION_LIFETIME_MINUTES = 15
STALE_RUNNING_MINUTES = 30
LINKEDIN_LOGIN_REQUIRED_STOP_REASON = "linkedin_login_required"


class ProfessionalCaptureAuthorizationRequest(BaseModel):
    confirmation_phrase: str
    user_present: bool


class ProfessionalCaptureOptions(BaseModel):
    max_sources: int = Field(default=8, ge=1, le=12)
    max_scroll_batches: int = Field(default=2, ge=0, le=20)
    max_items_per_source: int = Field(default=25, ge=1, le=200)
    timeout_seconds: int = Field(default=30, ge=10, le=120)
    stop_on_failure: bool = True


class ProfessionalCaptureCreateRequest(BaseModel):
    options: ProfessionalCaptureOptions = Field(default_factory=ProfessionalCaptureOptions)


class ProfessionalSourceProgress(BaseModel):
    source_id: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    completeness_status: str = ""
    detail: str = ""


class ProfessionalCaptureRunResponse(BaseModel):
    id: str
    mode: str
    status: str
    planned_sources: list[ProfessionalIntelligenceSource]
    safety_constraints: list[str]
    capture_options: ProfessionalCaptureOptions
    requested_at: datetime
    authorized_at: datetime | None
    authorization_expires_at: datetime | None
    user_present_confirmed: bool
    started_at: datetime | None
    completed_at: datetime | None
    stop_reason: str
    artifact_count: int = 0
    source_progress: list[ProfessionalSourceProgress]
    completed_source_count: int = 0
    total_source_count: int = 0
    current_source_id: str = ""
    cancel_requested: bool = False
    progress_updated_at: datetime | None = None


def comparable_datetimes(left: datetime, right: datetime) -> tuple[datetime, datetime]:
    if left.tzinfo is None and right.tzinfo is not None:
        right = right.replace(tzinfo=None)
    elif left.tzinfo is not None and right.tzinfo is None:
        left = left.replace(tzinfo=None)
    return left, right


def effective_capture_run_status(run: ProfessionalCaptureRun, now: datetime | None = None) -> str:
    current = now or utc_now()
    expires_at = run.authorization_expires_at
    if run.status == "authorized" and expires_at is not None:
        comparable_expiry, comparable_current = comparable_datetimes(expires_at, current)
        if comparable_expiry <= comparable_current:
            return "expired"
    return run.status


def is_linkedin_login_retry_run(run: ProfessionalCaptureRun) -> bool:
    return run.status == "failed" and run.stop_reason == LINKEDIN_LOGIN_REQUIRED_STOP_REASON


def recover_stale_professional_capture_runs(
    session: Session,
    *,
    now: datetime | None = None,
    stale_after: timedelta = timedelta(minutes=STALE_RUNNING_MINUTES),
) -> int:
    current = now or utc_now()
    running = session.scalars(
        select(ProfessionalCaptureRun).where(ProfessionalCaptureRun.status == "running")
    ).all()
    recovered = 0
    for run in running:
        stale = run.started_at is None
        if run.started_at is not None:
            comparable_started, comparable_current = comparable_datetimes(run.started_at, current)
            stale = comparable_started + stale_after <= comparable_current
        if not stale:
            continue
        run.status = "interrupted"
        run.completed_at = current
        run.current_source_id = ""
        run.progress_updated_at = current
        run.stop_reason = "stale_running_run_recovered"
        recovered += 1
    if recovered:
        session.commit()
    return recovered


def _source_progress(run: ProfessionalCaptureRun) -> list[ProfessionalSourceProgress]:
    raw = run.source_progress_json or "[]"
    return [ProfessionalSourceProgress.model_validate(item) for item in json.loads(raw)]


def _capture_options(run: ProfessionalCaptureRun) -> ProfessionalCaptureOptions:
    return ProfessionalCaptureOptions.model_validate_json(run.capture_options_json)


def _to_response(session: Session, run: ProfessionalCaptureRun) -> ProfessionalCaptureRunResponse:
    sources = [
        ProfessionalIntelligenceSource.model_validate(item)
        for item in json.loads(run.source_snapshot_json)
    ]
    artifact_count = session.scalar(
        select(func.count(ProfessionalCaptureArtifact.id)).where(
            ProfessionalCaptureArtifact.capture_run_id == run.id
        )
    )
    return ProfessionalCaptureRunResponse(
        id=run.id,
        mode=run.mode,
        status=effective_capture_run_status(run),
        planned_sources=sources,
        safety_constraints=list(json.loads(run.safety_constraints_json)),
        capture_options=_capture_options(run),
        requested_at=run.requested_at,
        authorized_at=run.authorized_at,
        authorization_expires_at=run.authorization_expires_at,
        user_present_confirmed=run.user_present_confirmed,
        started_at=run.started_at,
        completed_at=run.completed_at,
        stop_reason=run.stop_reason,
        artifact_count=int(artifact_count or 0),
        source_progress=_source_progress(run),
        completed_source_count=run.completed_source_count,
        total_source_count=len(sources),
        current_source_id=run.current_source_id,
        cancel_requested=run.cancel_requested,
        progress_updated_at=run.progress_updated_at,
    )


def _is_career_source(source: ProfessionalIntelligenceSource) -> bool:
    return str(source.category) == "career" or "job" in source.source_id.casefold()


def _select_bounded_sources(
    planned_sources: list[ProfessionalIntelligenceSource], max_sources: int
) -> list[ProfessionalIntelligenceSource]:
    """Select bounded capture sources with job/career evidence first.

    The Capture & Evidence workspace is primarily used to create job-review
    evidence. The previous implementation sliced registry order, so a one-source
    capture always captured the LinkedIn profile before any job page. Keep the
    registry order inside each bucket, but prioritize career/job sources so small
    capture runs exercise the Review Inbox workflow.
    """
    career_sources = [source for source in planned_sources if _is_career_source(source)]
    other_sources = [source for source in planned_sources if not _is_career_source(source)]
    return [*career_sources, *other_sources][:max_sources]


def create_professional_capture_preview_run(
    session: Session,
    request: ProfessionalCaptureCreateRequest | None = None,
) -> ProfessionalCaptureRunResponse:
    options = (request or ProfessionalCaptureCreateRequest()).options
    plan = build_professional_capture_plan(session)
    sources = _select_bounded_sources(plan.planned_sources, options.max_sources)
    run = ProfessionalCaptureRun(
        id=str(uuid4()),
        mode="preview_only",
        status="planned",
        source_snapshot_json=json.dumps([source.model_dump(mode="json") for source in sources]),
        safety_constraints_json=json.dumps(
            [
                *plan.safety_constraints,
                "bounded_source_count",
                "bounded_scroll_batches",
                "bounded_item_count",
                "bounded_source_timeout",
                "career_sources_prioritized_for_small_runs",
                "single_browser_process_per_run",
            ]
        ),
        capture_options_json=options.model_dump_json(),
        source_progress_json=json.dumps(
            [
                ProfessionalSourceProgress(source_id=source.source_id, status="pending").model_dump(
                    mode="json"
                )
                for source in sources
            ]
        ),
        completed_source_count=0,
        current_source_id="",
        cancel_requested=False,
        progress_updated_at=utc_now(),
        requested_at=utc_now(),
        authorized_at=None,
        authorization_expires_at=None,
        user_present_confirmed=False,
        started_at=None,
        completed_at=None,
        stop_reason="",
    )
    session.add(run)
    session.commit()
    return _to_response(session, run)


def list_professional_capture_runs(session: Session) -> list[ProfessionalCaptureRunResponse]:
    recover_stale_professional_capture_runs(session)
    runs = session.scalars(
        select(ProfessionalCaptureRun).order_by(ProfessionalCaptureRun.requested_at.desc())
    ).all()
    return [_to_response(session, run) for run in runs]


def get_professional_capture_run(session: Session, run_id: str) -> ProfessionalCaptureRunResponse:
    recover_stale_professional_capture_runs(session)
    run = session.get(ProfessionalCaptureRun, run_id)
    if run is None:
        raise JoltNotFoundError(f"Professional capture run {run_id} was not found.")
    return _to_response(session, run)


def authorize_professional_capture_run(
    session: Session,
    run_id: str,
    request: ProfessionalCaptureAuthorizationRequest,
) -> ProfessionalCaptureRunResponse:
    run = session.get(ProfessionalCaptureRun, run_id)
    if run is None:
        raise JoltNotFoundError(f"Professional capture run {run_id} was not found.")
    current_status = effective_capture_run_status(run)
    if current_status not in {"planned", "expired"} and not is_linkedin_login_retry_run(run):
        raise ValueError(
            "Only planned, expired, or LinkedIn-login-required capture runs can be authorized."
        )
    if request.confirmation_phrase != AUTHORIZATION_CONFIRMATION_PHRASE:
        raise ValueError("The exact authorization confirmation phrase is required.")
    if request.user_present is not True:
        raise ValueError("User-present confirmation is required.")

    authorized_at = utc_now()
    run.status = "authorized"
    run.authorized_at = authorized_at
    run.authorization_expires_at = authorized_at + timedelta(minutes=AUTHORIZATION_LIFETIME_MINUTES)
    run.user_present_confirmed = True
    run.completed_at = None
    run.current_source_id = ""
    run.cancel_requested = False
    run.stop_reason = ""
    run.progress_updated_at = authorized_at
    session.commit()
    return _to_response(session, run)


def cancel_professional_capture_run(
    session: Session, run_id: str
) -> ProfessionalCaptureRunResponse:
    run = session.get(ProfessionalCaptureRun, run_id)
    if run is None:
        raise JoltNotFoundError(f"Professional capture run {run_id} was not found.")
    if run.status == "running":
        run.cancel_requested = True
        run.progress_updated_at = utc_now()
        session.commit()
        return _to_response(session, run)
    if run.status not in {"planned", "authorized"}:
        raise ValueError("Only planned, authorized, or running capture runs can be cancelled.")
    run.status = "cancelled"
    run.completed_at = utc_now()
    run.progress_updated_at = run.completed_at
    run.stop_reason = "cancelled_by_user"
    session.commit()
    return _to_response(session, run)
