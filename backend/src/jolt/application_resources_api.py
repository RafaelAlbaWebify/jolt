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

SessionProvider = Callable[[], Iterator[Session]]


def build_application_resources_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["application-resources"])
    session_dependency = Depends(get_session)

    @router.get(
        "/api/applications/{application_id}/contacts",
        response_model=list[ContactResponse],
    )
    def application_contacts(
        application_id: str,
        session: Session = session_dependency,
    ) -> list[ContactResponse]:
        try:
            return list_contacts(session, application_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/api/applications/{application_id}/contacts",
        response_model=ContactResponse,
    )
    def add_application_contact(
        application_id: str,
        request: ContactRequest,
        session: Session = session_dependency,
    ) -> ContactResponse:
        try:
            return create_contact(session, application_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/api/application-contacts/{contact_id}/update",
        response_model=ContactResponse,
    )
    def edit_application_contact(
        contact_id: str,
        request: ContactRequest,
        session: Session = session_dependency,
    ) -> ContactResponse:
        try:
            return update_contact(session, contact_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get(
        "/api/applications/{application_id}/documents",
        response_model=list[DocumentResponse],
    )
    def application_documents(
        application_id: str,
        session: Session = session_dependency,
    ) -> list[DocumentResponse]:
        try:
            return list_documents(session, application_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/api/applications/{application_id}/documents",
        response_model=DocumentResponse,
    )
    def add_application_document(
        application_id: str,
        request: DocumentRequest,
        session: Session = session_dependency,
    ) -> DocumentResponse:
        try:
            return create_document(session, application_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/api/application-documents/{document_id}/update",
        response_model=DocumentResponse,
    )
    def edit_application_document(
        document_id: str,
        request: DocumentRequest,
        session: Session = session_dependency,
    ) -> DocumentResponse:
        try:
            return update_document(session, document_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
