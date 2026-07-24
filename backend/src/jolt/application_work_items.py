from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.application_records import ApplicationInterview, ApplicationTask
from jolt.database import Application, ApplicationEvent, utc_now

TaskStatus = Literal["open", "completed"]
InterviewStatus = Literal["scheduled", "completed", "cancelled"]
InterviewType = Literal[
    "recruiter_screen",
    "technical_interview",
    "hiring_manager_interview",
    "final_interview",
    "other",
]


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    notes: str = ""
    due_at: datetime | None = None


class TaskUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    notes: str = ""
    due_at: datetime | None = None


class TaskResponse(BaseModel):
    task_id: str
    application_id: str
    title: str
    notes: str
    due_at: str | None
    status: TaskStatus
    completed_at: str | None
    created_at: str
    updated_at: str


class InterviewCreateRequest(BaseModel):
    interview_type: InterviewType
    scheduled_at: datetime
    timezone: str = Field(default="UTC", min_length=1, max_length=80)
    format_location: str = ""
    participants: str = ""
    preparation_notes: str = ""


class InterviewUpdateRequest(InterviewCreateRequest):
    outcome_notes: str = ""


class InterviewCompleteRequest(BaseModel):
    outcome_notes: str = ""


class InterviewResponse(BaseModel):
    interview_id: str
    application_id: str
    interview_type: InterviewType
    scheduled_at: str
    timezone: str
    format_location: str
    participants: str
    preparation_notes: str
    outcome_notes: str
    status: InterviewStatus
    completed_at: str | None
    created_at: str
    updated_at: str


def _application(session: Session, application_id: str) -> Application:
    application = session.get(Application, application_id)
    if application is None:
        raise LookupError("Application was not found.")
    return application


def _task_response(task: ApplicationTask) -> TaskResponse:
    return TaskResponse(
        task_id=task.id,
        application_id=task.application_id,
        title=task.title,
        notes=task.notes,
        due_at=task.due_at.isoformat() if task.due_at else None,
        status=task.status,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
    )


def _interview_response(interview: ApplicationInterview) -> InterviewResponse:
    return InterviewResponse(
        interview_id=interview.id,
        application_id=interview.application_id,
        interview_type=interview.interview_type,
        scheduled_at=interview.scheduled_at.isoformat(),
        timezone=interview.timezone,
        format_location=interview.format_location,
        participants=interview.participants,
        preparation_notes=interview.preparation_notes,
        outcome_notes=interview.outcome_notes,
        status=interview.status,
        completed_at=interview.completed_at.isoformat() if interview.completed_at else None,
        created_at=interview.created_at.isoformat(),
        updated_at=interview.updated_at.isoformat(),
    )


def _event(
    application_id: str,
    event_type: str,
    from_status: str,
    to_status: str,
    notes: str,
    occurred_at: datetime,
) -> ApplicationEvent:
    return ApplicationEvent(
        id=str(uuid4()),
        application_id=application_id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        notes=notes,
        occurred_at=occurred_at,
    )


def list_tasks(session: Session, application_id: str) -> list[TaskResponse]:
    _application(session, application_id)
    tasks = session.scalars(
        select(ApplicationTask)
        .where(ApplicationTask.application_id == application_id)
        .order_by(ApplicationTask.status, ApplicationTask.due_at, ApplicationTask.created_at)
    ).all()
    return [_task_response(task) for task in tasks]


def create_task(session: Session, application_id: str, request: TaskCreateRequest) -> TaskResponse:
    _application(session, application_id)
    now = utc_now()
    task = ApplicationTask(
        id=str(uuid4()),
        application_id=application_id,
        title=request.title.strip(),
        notes=request.notes.strip(),
        due_at=request.due_at,
        status="open",
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    session.add(task)
    session.add(_event(application_id, "task_created", "", "open", task.title, now))
    session.commit()
    return _task_response(task)


def update_task(session: Session, task_id: str, request: TaskUpdateRequest) -> TaskResponse:
    task = session.get(ApplicationTask, task_id)
    if task is None:
        raise LookupError("Application task was not found.")
    now = utc_now()
    task.title = request.title.strip()
    task.notes = request.notes.strip()
    task.due_at = request.due_at
    task.updated_at = now
    session.add(
        _event(task.application_id, "task_updated", task.status, task.status, task.title, now)
    )
    session.commit()
    return _task_response(task)


def set_task_status(session: Session, task_id: str, status: TaskStatus) -> TaskResponse:
    task = session.get(ApplicationTask, task_id)
    if task is None:
        raise LookupError("Application task was not found.")
    if task.status == status:
        return _task_response(task)
    now = utc_now()
    previous = task.status
    task.status = status
    task.completed_at = now if status == "completed" else None
    task.updated_at = now
    session.add(
        _event(
            task.application_id,
            "task_completed" if status == "completed" else "task_reopened",
            previous,
            status,
            task.title,
            now,
        )
    )
    session.commit()
    return _task_response(task)


def list_interviews(session: Session, application_id: str) -> list[InterviewResponse]:
    _application(session, application_id)
    interviews = session.scalars(
        select(ApplicationInterview)
        .where(ApplicationInterview.application_id == application_id)
        .order_by(ApplicationInterview.scheduled_at)
    ).all()
    return [_interview_response(interview) for interview in interviews]


def create_interview(
    session: Session, application_id: str, request: InterviewCreateRequest
) -> InterviewResponse:
    _application(session, application_id)
    now = utc_now()
    interview = ApplicationInterview(
        id=str(uuid4()),
        application_id=application_id,
        interview_type=request.interview_type,
        scheduled_at=request.scheduled_at,
        timezone=request.timezone.strip(),
        format_location=request.format_location.strip(),
        participants=request.participants.strip(),
        preparation_notes=request.preparation_notes.strip(),
        outcome_notes="",
        status="scheduled",
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    session.add(interview)
    session.add(
        _event(
            application_id,
            "interview_created",
            "",
            "scheduled",
            f"{request.interview_type}: {request.scheduled_at.isoformat()}",
            now,
        )
    )
    session.commit()
    return _interview_response(interview)


def update_interview(
    session: Session, interview_id: str, request: InterviewUpdateRequest
) -> InterviewResponse:
    interview = session.get(ApplicationInterview, interview_id)
    if interview is None:
        raise LookupError("Application interview was not found.")
    now = utc_now()
    interview.interview_type = request.interview_type
    interview.scheduled_at = request.scheduled_at
    interview.timezone = request.timezone.strip()
    interview.format_location = request.format_location.strip()
    interview.participants = request.participants.strip()
    interview.preparation_notes = request.preparation_notes.strip()
    interview.outcome_notes = request.outcome_notes.strip()
    interview.updated_at = now
    session.add(
        _event(
            interview.application_id,
            "interview_updated",
            interview.status,
            interview.status,
            f"{request.interview_type}: {request.scheduled_at.isoformat()}",
            now,
        )
    )
    session.commit()
    return _interview_response(interview)


def set_interview_status(
    session: Session,
    interview_id: str,
    status: InterviewStatus,
    outcome_notes: str = "",
) -> InterviewResponse:
    interview = session.get(ApplicationInterview, interview_id)
    if interview is None:
        raise LookupError("Application interview was not found.")
    if interview.status == status and not outcome_notes.strip():
        return _interview_response(interview)
    now = utc_now()
    previous = interview.status
    interview.status = status
    interview.completed_at = now if status == "completed" else None
    if outcome_notes.strip():
        interview.outcome_notes = outcome_notes.strip()
    interview.updated_at = now
    session.add(
        _event(
            interview.application_id,
            f"interview_{status}",
            previous,
            status,
            interview.outcome_notes or interview.interview_type,
            now,
        )
    )
    session.commit()
    return _interview_response(interview)
