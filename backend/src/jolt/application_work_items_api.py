from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.application_resources import (
    ContactRequest,
    ContactResponse,
    DocumentRequest,
    DocumentResponse,
    create_contact,
    create_document,
    list_contacts,
    list_documents,
    update_contact,
    update_document,
)
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
from jolt.professional_intelligence_sources import (
    ProfessionalIntelligenceSource,
    list_professional_intelligence_sources,
)

SessionProvider = Callable[[], Iterator[Session]]


def build_application_work_items_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["application-work-items"])
    session_dependency = Depends(get_session)

    @router.get(
        "/api/professional-intelligence/sources",
        response_model=list[ProfessionalIntelligenceSource],
        tags=["professional-intelligence"],
    )
    def professional_intelligence_sources() -> list[ProfessionalIntelligenceSource]:
        return list_professional_intelligence_sources()

    @router.get("/api/applications/{application_id}/tasks", response_model=list[TaskResponse])
    def application_tasks(
        application_id: str, session: Session = session_dependency
    ) -> list[TaskResponse]:
        try:
            return list_tasks(session, application_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/applications/{application_id}/tasks", response_model=TaskResponse)
    def add_application_task(
        application_id: str, request: TaskCreateRequest, session: Session = session_dependency
    ) -> TaskResponse:
        try:
            return create_task(session, application_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/application-tasks/{task_id}/update", response_model=TaskResponse)
    def edit_application_task(
        task_id: str, request: TaskUpdateRequest, session: Session = session_dependency
    ) -> TaskResponse:
        try:
            return update_task(session, task_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/application-tasks/{task_id}/complete", response_model=TaskResponse)
    def complete_application_task(
        task_id: str, session: Session = session_dependency
    ) -> TaskResponse:
        try:
            return set_task_status(session, task_id, "completed")
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/application-tasks/{task_id}/reopen", response_model=TaskResponse)
    def reopen_application_task(
        task_id: str, session: Session = session_dependency
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
        application_id: str, session: Session = session_dependency
    ) -> list[InterviewResponse]:
        try:
            return list_interviews(session, application_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/applications/{application_id}/interviews", response_model=InterviewResponse)
    def add_application_interview(
        application_id: str,
        request: InterviewCreateRequest,
        session: Session = session_dependency,
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
        session: Session = session_dependency,
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
        session: Session = session_dependency,
    ) -> InterviewResponse:
        try:
            return set_interview_status(session, interview_id, "completed", request.outcome_notes)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/api/application-interviews/{interview_id}/cancel",
        response_model=InterviewResponse,
    )
    def cancel_application_interview(
        interview_id: str,
        request: InterviewCompleteRequest,
        session: Session = session_dependency,
    ) -> InterviewResponse:
        try:
            return set_interview_status(session, interview_id, "cancelled", request.outcome_notes)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/api/applications/{application_id}/contacts", response_model=list[ContactResponse])
    def application_contacts(
        application_id: str, session: Session = session_dependency
    ) -> list[ContactResponse]:
        try:
            return list_contacts(session, application_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/applications/{application_id}/contacts", response_model=ContactResponse)
    def add_application_contact(
        application_id: str, request: ContactRequest, session: Session = session_dependency
    ) -> ContactResponse:
        try:
            return create_contact(session, application_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/application-contacts/{contact_id}/update", response_model=ContactResponse)
    def edit_application_contact(
        contact_id: str, request: ContactRequest, session: Session = session_dependency
    ) -> ContactResponse:
        try:
            return update_contact(session, contact_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get(
        "/api/applications/{application_id}/documents", response_model=list[DocumentResponse]
    )
    def application_documents(
        application_id: str, session: Session = session_dependency
    ) -> list[DocumentResponse]:
        try:
            return list_documents(session, application_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/applications/{application_id}/documents", response_model=DocumentResponse)
    def add_application_document(
        application_id: str, request: DocumentRequest, session: Session = session_dependency
    ) -> DocumentResponse:
        try:
            return create_document(session, application_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/application-documents/{document_id}/update", response_model=DocumentResponse)
    def edit_application_document(
        document_id: str, request: DocumentRequest, session: Session = session_dependency
    ) -> DocumentResponse:
        try:
            return update_document(session, document_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
