from __future__ import annotations

from typing import Literal, cast
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.application_records import ApplicationContact, ApplicationDocument
from jolt.database import Application, ApplicationEvent, utc_now

DocumentType = Literal["resume", "cover_letter", "preparation_pack", "portfolio", "certificate", "other"]
DocumentStatus = Literal["draft", "ready", "submitted", "superseded"]


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    role: str = ""
    company: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    notes: str = ""


class ContactResponse(ContactRequest):
    contact_id: str
    application_id: str
    created_at: str
    updated_at: str


class DocumentRequest(BaseModel):
    document_type: DocumentType
    title: str = Field(min_length=1, max_length=240)
    file_path: str = ""
    source_url: str = ""
    status: DocumentStatus = "draft"
    notes: str = ""


class DocumentResponse(DocumentRequest):
    document_id: str
    application_id: str
    created_at: str
    updated_at: str


def _application(session: Session, application_id: str) -> Application:
    application = session.get(Application, application_id)
    if application is None:
        raise LookupError("Application was not found.")
    return application


def _event(application_id: str, event_type: str, notes: str) -> ApplicationEvent:
    now = utc_now()
    return ApplicationEvent(
        id=str(uuid4()),
        application_id=application_id,
        event_type=event_type,
        from_status="",
        to_status="recorded",
        notes=notes,
        occurred_at=now,
    )


def _contact_response(contact: ApplicationContact) -> ContactResponse:
    return ContactResponse(
        contact_id=contact.id,
        application_id=contact.application_id,
        name=contact.name,
        role=contact.role,
        company=contact.company,
        email=contact.email,
        phone=contact.phone,
        linkedin_url=contact.linkedin_url,
        notes=contact.notes,
        created_at=contact.created_at.isoformat(),
        updated_at=contact.updated_at.isoformat(),
    )


def _document_response(document: ApplicationDocument) -> DocumentResponse:
    return DocumentResponse(
        document_id=document.id,
        application_id=document.application_id,
        document_type=cast(DocumentType, document.document_type),
        title=document.title,
        file_path=document.file_path,
        source_url=document.source_url,
        status=cast(DocumentStatus, document.status),
        notes=document.notes,
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat(),
    )


def list_contacts(session: Session, application_id: str) -> list[ContactResponse]:
    _application(session, application_id)
    contacts = session.scalars(
        select(ApplicationContact)
        .where(ApplicationContact.application_id == application_id)
        .order_by(ApplicationContact.name)
    ).all()
    return [_contact_response(contact) for contact in contacts]


def create_contact(session: Session, application_id: str, request: ContactRequest) -> ContactResponse:
    _application(session, application_id)
    now = utc_now()
    contact = ApplicationContact(
        id=str(uuid4()),
        application_id=application_id,
        name=request.name.strip(),
        role=request.role.strip(),
        company=request.company.strip(),
        email=request.email.strip(),
        phone=request.phone.strip(),
        linkedin_url=request.linkedin_url.strip(),
        notes=request.notes.strip(),
        created_at=now,
        updated_at=now,
    )
    session.add(contact)
    session.add(_event(application_id, "contact_created", contact.name))
    session.commit()
    return _contact_response(contact)


def update_contact(session: Session, contact_id: str, request: ContactRequest) -> ContactResponse:
    contact = session.get(ApplicationContact, contact_id)
    if contact is None:
        raise LookupError("Application contact was not found.")
    contact.name = request.name.strip()
    contact.role = request.role.strip()
    contact.company = request.company.strip()
    contact.email = request.email.strip()
    contact.phone = request.phone.strip()
    contact.linkedin_url = request.linkedin_url.strip()
    contact.notes = request.notes.strip()
    contact.updated_at = utc_now()
    session.add(_event(contact.application_id, "contact_updated", contact.name))
    session.commit()
    return _contact_response(contact)


def list_documents(session: Session, application_id: str) -> list[DocumentResponse]:
    _application(session, application_id)
    documents = session.scalars(
        select(ApplicationDocument)
        .where(ApplicationDocument.application_id == application_id)
        .order_by(ApplicationDocument.document_type, ApplicationDocument.title)
    ).all()
    return [_document_response(document) for document in documents]


def create_document(session: Session, application_id: str, request: DocumentRequest) -> DocumentResponse:
    _application(session, application_id)
    now = utc_now()
    document = ApplicationDocument(
        id=str(uuid4()),
        application_id=application_id,
        document_type=request.document_type,
        title=request.title.strip(),
        file_path=request.file_path.strip(),
        source_url=request.source_url.strip(),
        status=request.status,
        notes=request.notes.strip(),
        created_at=now,
        updated_at=now,
    )
    session.add(document)
    session.add(_event(application_id, "document_created", document.title))
    session.commit()
    return _document_response(document)


def update_document(session: Session, document_id: str, request: DocumentRequest) -> DocumentResponse:
    document = session.get(ApplicationDocument, document_id)
    if document is None:
        raise LookupError("Application document was not found.")
    document.document_type = request.document_type
    document.title = request.title.strip()
    document.file_path = request.file_path.strip()
    document.source_url = request.source_url.strip()
    document.status = request.status
    document.notes = request.notes.strip()
    document.updated_at = utc_now()
    session.add(_event(document.application_id, "document_updated", document.title))
    session.commit()
    return _document_response(document)
