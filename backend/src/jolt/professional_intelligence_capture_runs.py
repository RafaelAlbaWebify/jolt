from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import utc_now
from jolt.professional_intelligence_capture_plan import build_professional_capture_plan
from jolt.professional_intelligence_records import ProfessionalCaptureRun
from jolt.professional_intelligence_sources import ProfessionalIntelligenceSource


class ProfessionalCaptureRunResponse(BaseModel):
    id: str
    mode: str
    status: str
    planned_sources: list[ProfessionalIntelligenceSource]
    safety_constraints: list[str]
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    stop_reason: str
    artifact_count: int = 0


def _to_response(run: ProfessionalCaptureRun) -> ProfessionalCaptureRunResponse:
    sources = [ProfessionalIntelligenceSource.model_validate(item) for item in json.loads(run.source_snapshot_json)]
    return ProfessionalCaptureRunResponse(
        id=run.id,
        mode=run.mode,
        status=run.status,
        planned_sources=sources,
        safety_constraints=list(json.loads(run.safety_constraints_json)),
        requested_at=run.requested_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        stop_reason=run.stop_reason,
    )


def create_professional_capture_preview_run(session: Session) -> ProfessionalCaptureRunResponse:
    plan = build_professional_capture_plan(session)
    run = ProfessionalCaptureRun(
        id=str(uuid4()),
        mode="preview_only",
        status="planned",
        source_snapshot_json=json.dumps([source.model_dump(mode="json") for source in plan.planned_sources]),
        safety_constraints_json=json.dumps(plan.safety_constraints),
        requested_at=utc_now(),
        started_at=None,
        completed_at=None,
        stop_reason="",
    )
    session.add(run)
    session.commit()
    return _to_response(run)


def list_professional_capture_runs(session: Session) -> list[ProfessionalCaptureRunResponse]:
    runs = session.scalars(
        select(ProfessionalCaptureRun).order_by(ProfessionalCaptureRun.requested_at.desc())
    ).all()
    return [_to_response(run) for run in runs]


def get_professional_capture_run(session: Session, run_id: str) -> ProfessionalCaptureRunResponse:
    run = session.get(ProfessionalCaptureRun, run_id)
    if run is None:
        raise LookupError(f"Professional capture run {run_id} was not found.")
    return _to_response(run)


def cancel_professional_capture_run(session: Session, run_id: str) -> ProfessionalCaptureRunResponse:
    run = session.get(ProfessionalCaptureRun, run_id)
    if run is None:
        raise LookupError(f"Professional capture run {run_id} was not found.")
    if run.status != "planned":
        raise ValueError("Only planned preview runs can be cancelled.")
    run.status = "cancelled"
    run.completed_at = utc_now()
    run.stop_reason = "cancelled_by_user"
    session.commit()
    return _to_response(run)
