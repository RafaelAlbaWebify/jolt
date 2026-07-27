from __future__ import annotations

import re
from typing import Literal, cast
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.application_records import ApplicationContact, ApplicationDocument
from jolt.database import Application, ApplicationEvent, utc_now

DocumentType = Literal[
    "resume", "cover_letter", "preparation_pack", "portfolio", "certificate", "other"
]
DocumentStatus = Literal["draft", "ready", "submitted", "superseded"]
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _optional_text(value: str) -> str:
    return value.strip()


def _optional_email(value: str) -> str:
    normalized = value.strip()
    if normalized and not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("Contact email must be a valid email address.")
    return normalized


def _optional_https_url(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    parsed = urlsplit(normalized)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"{field_name} must be a public HTTPS URL.")
    return normalized


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    role: str = Field(default="", max_length=240)
    company: str = Field(default="", max_length=240)
    email: str = Field(default="", max_length=320)
    phone: str = Field(default="", max_length=80)
    linkedin_url: str = Field(default="", max_length=2048)
    notes: str = Field(default="", max_length=4000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Contact name is required.")
        return normalized

    @field_validator("role", "company", "phone", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str) -> str:
        return _optional_text(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _optional_email(value)

    @field_validator("linkedin_url")
    @classmethod
    def normalize_linkedin_url(cls, value: str) -> str:
        normalized = _optional_https_url(value, "LinkedIn URL")
        if normalized and urlsplit(normalized).hostname not in {"linkedin.com", "www.linkedin.com"}:
            raise ValueError("LinkedIn URL must use linkedin.com.")
        return normalized


class ContactResponse(ContactRequest):
    contact_id: str
    application_id: str
    created_at: str
    updated_at: str


class DocumentRequest(BaseModel):
    document_type: DocumentType
    title: str = Field(min_length=1, max_length=240)
    file_path: str = ""
    source_url: str = Field(default="", max_length=2048)
    status: DocumentStatus = "draft"
    notes: str = ""

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Document title is required.")
        return normalized

    @field_validator("file_path", "notes")
    @classmethod
    def normalize_document_text(cls, value: str) -> str:
        return _optional_text(value)

    @field_validator("source_url")
    @classmethod
    def normalize_source_url(cls, value: str) -> str:
        return _optional_https_url(value, "Document source URL")


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


def _changed_fields(before: dict[str, str], after: dict[str, str]) -> str:
    changes = [
        f"{field}: {before[field] or '(blank)'} -> {after[field] or '(blank)'}"
        for field in before
        if before[field] != after[field]
    ]
    return "; ".join(changes) if changes else "No field values changed."


def _contact_values(contact: ApplicationContact) -> dict[str, str]:
    return {
        "name": contact.name,
        "role": contact.role,
        "company": contact.company,
        "email": contact.email,
        "phone": contact.phone,
        "linkedin_url": contact.linkedin_url,
        "notes": contact.notes,
    }


def _contact_response(contact: ApplicationContact) -> ContactResponse:
    return ContactResponse(
        contact_id=contact.id,
        application_id=contact.application_id,
        **_contact_values(contact),
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


def create_contact(
    session: Session, application_id: str, request: ContactRequest
) -> ContactResponse:
    _application(session, application_id)
    now = utc_now()
    contact = ApplicationContact(
        id=str(uuid4()),
        application_id=application_id,
        name=request.name,
        role=request.role,
        company=request.company,
        email=request.email,
        phone=request.phone,
        linkedin_url=request.linkedin_url,
        notes=request.notes,
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
    before = _contact_values(contact)
    contact.name = request.name
    contact.role = request.role
    contact.company = request.company
    contact.email = request.email
    contact.phone = request.phone
    contact.linkedin_url = request.linkedin_url
    contact.notes = request.notes
    contact.updated_at = utc_now()
    after = _contact_values(contact)
    session.add(
        _event(
            contact.application_id,
            "contact_updated",
            f"Contact {contact.id} corrected. {_changed_fields(before, after)}",
        )
    )
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


def create_document(
    session: Session, application_id: str, request: DocumentRequest
) -> DocumentResponse:
    _application(session, application_id)
    now = utc_now()
    document = ApplicationDocument(
        id=str(uuid4()),
        application_id=application_id,
        document_type=request.document_type,
        title=request.title,
        file_path=request.file_path,
        source_url=request.source_url,
        status=request.status,
        notes=request.notes,
        created_at=now,
        updated_at=now,
    )
    session.add(document)
    session.add(_event(application_id, "document_created", document.title))
    session.commit()
    return _document_response(document)


def update_document(
    session: Session, document_id: str, request: DocumentRequest
) -> DocumentResponse:
    document = session.get(ApplicationDocument, document_id)
    if document is None:
        raise LookupError("Application document was not found.")
    document.document_type = request.document_type
    document.title = request.title
    document.file_path = request.file_path
    document.source_url = request.source_url
    document.status = request.status
    document.notes = request.notes
    document.updated_at = utc_now()
    session.add(_event(document.application_id, "document_updated", document.title))
    session.commit()
    return _document_response(document)
