from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.application_work_items import (
    InterviewCompleteRequest,
    InterviewCreateRequest,
    InterviewResponse,
    InterviewUpdateRequest,
    TaskCreateRequest,
    TaskResponse,
    TaskUpdateRequest,
    create_interview,
    create_task,
    list_interviews,
    list_tasks,
    set_interview_status,
    set_task_status,
    update_interview,
    update_task,
)

SessionProvider = Callable[[], Iterator[Session]]


def build_application_work_items_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["application-work-items"])

    @router.get(
        "/api/applications/{application_id}/tasks",
        response_model=list[TaskResponse],
    )
    def application_tasks(
        application_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> list[TaskResponse]:
        try:
            return list_tasks(session, application_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/api/applications/{application_id}/tasks",
        response_model=TaskResponse,
    )
    def add_application_task(
        application_id: str,
        request: TaskCreateRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> TaskResponse:
        try:
            return create_task(session, application_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/application-tasks/{task_id}/update", response_model=TaskResponse)
    def edit_application_task(
        task_id: str,
        request: TaskUpdateRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> TaskResponse:
        try:
            return update_task(session, task_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/application-tasks/{task_id}/complete", response_model=TaskResponse)
    def complete_application_task(
        task_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> TaskResponse:
        try:
            return set_task_status(session, task_id, "completed")
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/application-tasks/{task_id}/reopen", response_model=TaskResponse)
    def reopen_application_task(
        task_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> TaskResponse:
        try:
            return set_task_status(session, task_id, "open")
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get(
        "/api/applications/{application_id}/interviews",
        response_model=list[InterviewResponse],
    )
    def application_interviews(
        application_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> list[InterviewResponse]:
        try:
            return list_interviews(session, application_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/api/applications/{application_id}/interviews",
        response_model=InterviewResponse,
    )
    def add_application_interview(
        application_id: str,
        request: InterviewCreateRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> InterviewResponse:
        try:
            return create_interview(session, application_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/api/application-interviews/{interview_id}/update",
        response_model=InterviewResponse,
    )
    def edit_application_interview(
        interview_id: str,
        request: InterviewUpdateRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> InterviewResponse:
        try:
            return update_interview(session, interview_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/api/application-interviews/{interview_id}/complete",
        response_model=InterviewResponse,
    )
    def complete_application_interview(
        interview_id: str,
        request: InterviewCompleteRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> InterviewResponse:
        try:
            return set_interview_status(
                session, interview_id, "completed", request.outcome_notes
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/api/application-interviews/{interview_id}/cancel",
        response_model=InterviewResponse,
    )
    def cancel_application_interview(
        interview_id: str,
        request: InterviewCompleteRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> InterviewResponse:
        try:
            return set_interview_status(
                session, interview_id, "cancelled", request.outcome_notes
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
