from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import NoReturn
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from jolt.application_archival import ArchivedApplicationReadOnlyError
from jolt.application_resources import (
    ContactRequest,
    ContactResponse,
    DocumentRequest,
    DocumentResponse,
    create_contact,
    create_document,
    get_document_file,
    list_contacts,
    list_documents,
    store_document_file,
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
from jolt.errors import JoltNotFoundError
from jolt.professional_intelligence_registry import (
    ProfessionalSourceUpdateRequest,
    list_configured_professional_sources,
    reset_professional_source,
    update_professional_source,
)
from jolt.professional_intelligence_sources import ProfessionalIntelligenceSource

SessionProvider = Callable[[], Iterator[Session]]


def _raise_read_only_conflict(exc: ArchivedApplicationReadOnlyError) -> NoReturn:
    raise HTTPException(status_code=409, detail=str(exc)) from exc


def build_application_work_items_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["application-work-items"])
    session_dependency = Depends(get_session)

    @router.get(
        "/api/professional-intelligence/sources",
        response_model=list[ProfessionalIntelligenceSource],
        tags=["professional-intelligence"],
    )
    def professional_intelligence_sources(
        session: Session = session_dependency,
    ) -> list[ProfessionalIntelligenceSource]:
        return list_configured_professional_sources(session)

    @router.post(
        "/api/professional-intelligence/sources/{source_id}/update",
        response_model=ProfessionalIntelligenceSource,
        tags=["professional-intelligence"],
    )
    def edit_professional_intelligence_source(
        source_id: str,
        request: ProfessionalSourceUpdateRequest,
        session: Session = session_dependency,
    ) -> ProfessionalIntelligenceSource:
        try:
            return update_professional_source(session, source_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post(
        "/api/professional-intelligence/sources/{source_id}/reset",
        response_model=ProfessionalIntelligenceSource,
        tags=["professional-intelligence"],
    )
    def reset_professional_intelligence_source(
        source_id: str,
        session: Session = session_dependency,
    ) -> ProfessionalIntelligenceSource:
        try:
            return reset_professional_source(session, source_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/api/applications/{application_id}/tasks", response_model=list[TaskResponse])
    def application_tasks(
        application_id: str, session: Session = session_dependency
    ) -> list[TaskResponse]:
        try:
            return list_tasks(session, application_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/applications/{application_id}/tasks", response_model=TaskResponse)
    def add_application_task(
        application_id: str, request: TaskCreateRequest, session: Session = session_dependency
    ) -> TaskResponse:
        try:
            return create_task(session, application_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)

    @router.post("/api/application-tasks/{task_id}/update", response_model=TaskResponse)
    def edit_application_task(
        task_id: str, request: TaskUpdateRequest, session: Session = session_dependency
    ) -> TaskResponse:
        try:
            return update_task(session, task_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)

    @router.post("/api/application-tasks/{task_id}/complete", response_model=TaskResponse)
    def complete_application_task(
        task_id: str, session: Session = session_dependency
    ) -> TaskResponse:
        try:
            return set_task_status(session, task_id, "completed")
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)

    @router.post("/api/application-tasks/{task_id}/reopen", response_model=TaskResponse)
    def reopen_application_task(
        task_id: str, session: Session = session_dependency
    ) -> TaskResponse:
        try:
            return set_task_status(session, task_id, "open")
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)

    @router.get(
        "/api/applications/{application_id}/interviews",
        response_model=list[InterviewResponse],
    )
    def application_interviews(
        application_id: str, session: Session = session_dependency
    ) -> list[InterviewResponse]:
        try:
            return list_interviews(session, application_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/applications/{application_id}/interviews", response_model=InterviewResponse)
    def add_application_interview(
        application_id: str,
        request: InterviewCreateRequest,
        session: Session = session_dependency,
    ) -> InterviewResponse:
        try:
            return create_interview(session, application_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)

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
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)

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
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)

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
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)

    @router.get("/api/applications/{application_id}/contacts", response_model=list[ContactResponse])
    def application_contacts(
        application_id: str, session: Session = session_dependency
    ) -> list[ContactResponse]:
        try:
            return list_contacts(session, application_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/applications/{application_id}/contacts", response_model=ContactResponse)
    def add_application_contact(
        application_id: str, request: ContactRequest, session: Session = session_dependency
    ) -> ContactResponse:
        try:
            return create_contact(session, application_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)

    @router.post("/api/application-contacts/{contact_id}/update", response_model=ContactResponse)
    def edit_application_contact(
        contact_id: str, request: ContactRequest, session: Session = session_dependency
    ) -> ContactResponse:
        try:
            return update_contact(session, contact_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)

    @router.get(
        "/api/applications/{application_id}/documents", response_model=list[DocumentResponse]
    )
    def application_documents(
        application_id: str, session: Session = session_dependency
    ) -> list[DocumentResponse]:
        try:
            return list_documents(session, application_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/applications/{application_id}/documents", response_model=DocumentResponse)
    def add_application_document(
        application_id: str, request: DocumentRequest, session: Session = session_dependency
    ) -> DocumentResponse:
        try:
            return create_document(session, application_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)

    @router.post("/api/application-documents/{document_id}/update", response_model=DocumentResponse)
    def edit_application_document(
        document_id: str, request: DocumentRequest, session: Session = session_dependency
    ) -> DocumentResponse:
        try:
            return update_document(session, document_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)

    @router.post(
        "/api/application-documents/{document_id}/file",
        response_model=DocumentResponse,
    )
    async def upload_application_document_file(
        document_id: str,
        request: Request,
        filename: str,
        session: Session = session_dependency,
    ) -> DocumentResponse:
        content = await request.body()
        mime_type = request.headers.get("content-type", "application/octet-stream")
        mime_type = mime_type.split(";", 1)[0].strip()

        try:
            return store_document_file(
                session,
                document_id,
                filename=filename,
                mime_type=mime_type,
                content=content,
            )
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArchivedApplicationReadOnlyError as exc:
            _raise_read_only_conflict(exc)
        except ValueError as exc:
            status_code = 413 if "10 MB" in str(exc) else 422
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    @router.get("/api/application-documents/{document_id}/file")
    def download_application_document_file(
        document_id: str,
        session: Session = session_dependency,
    ) -> Response:
        try:
            filename, mime_type, content = get_document_file(session, document_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        encoded_filename = quote(filename)
        return Response(
            content=content,
            media_type=mime_type,
            headers={"Content-Disposition": ("attachment; filename*=UTF-8''" + encoded_filename)},
        )

    return router
