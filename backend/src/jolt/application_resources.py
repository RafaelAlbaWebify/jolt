from __future__ import annotations

import hashlib
import re
from typing import Literal, cast
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.application_archival import require_writable_application
from jolt.application_records import ApplicationContact, ApplicationDocument
from jolt.database import Application, ApplicationEvent, utc_now

DocumentType = Literal[
    "resume", "cover_letter", "preparation_pack", "portfolio", "certificate", "other"
]
DocumentStatus = Literal["draft", "ready", "submitted", "superseded"]
MAX_DOCUMENT_FILE_BYTES = 10 * 1024 * 1024
_ALLOWED_DOCUMENT_FILE_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}
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
    file_path: str = Field(default="", max_length=2048)
    source_url: str = Field(default="", max_length=2048)
    status: DocumentStatus = "draft"
    notes: str = Field(default="", max_length=4000)

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
    stored_filename: str = ""
    mime_type: str = ""
    file_size: int = 0
    file_sha256: str = ""
    has_file: bool = False
    created_at: str
    updated_at: str


def _application(session: Session, application_id: str) -> Application:
    application = session.get(Application, application_id)
    if application is None:
        raise LookupError("Application was not found.")
    return application


def _event(application_id: str, event_type: str, notes: str) -> ApplicationEvent:
    return ApplicationEvent(
        id=str(uuid4()),
        application_id=application_id,
        event_type=event_type,
        from_status="",
        to_status="recorded",
        notes=notes,
        occurred_at=utc_now(),
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


def _document_values(document: ApplicationDocument) -> dict[str, str]:
    return {
        "document_type": document.document_type,
        "title": document.title,
        "file_path": document.file_path,
        "source_url": document.source_url,
        "status": document.status,
        "notes": document.notes,
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
        stored_filename=document.stored_filename,
        mime_type=document.mime_type,
        file_size=document.file_size,
        file_sha256=document.file_sha256,
        has_file=document.file_content is not None,
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
    require_writable_application(session, application_id)
    now = utc_now()
    contact = ApplicationContact(
        id=str(uuid4()),
        application_id=application_id,
        **request.model_dump(),
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
    require_writable_application(session, contact.application_id)
    before = _contact_values(contact)
    for field, value in request.model_dump().items():
        setattr(contact, field, value)
    contact.updated_at = utc_now()
    session.add(
        _event(
            contact.application_id,
            "contact_updated",
            f"Contact {contact.id} corrected. {_changed_fields(before, _contact_values(contact))}",
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
    require_writable_application(session, application_id)
    now = utc_now()
    document = ApplicationDocument(
        id=str(uuid4()),
        application_id=application_id,
        **request.model_dump(),
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
    require_writable_application(session, document.application_id)
    before = _document_values(document)
    for field, value in request.model_dump().items():
        setattr(document, field, value)
    document.updated_at = utc_now()
    session.add(
        _event(
            document.application_id,
            "document_updated",
            f"Document {document.id} corrected. {_changed_fields(before, _document_values(document))}",
        )
    )
    session.commit()
    return _document_response(document)


def _safe_document_filename(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    filename = normalized.rsplit("/", 1)[-1]

    if (
        not filename
        or filename in {".", ".."}
        or "\r" in filename
        or "\n" in filename
        or '"' in filename
    ):
        raise ValueError("Document filename is invalid.")

    suffix = "." + filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""

    if suffix not in _ALLOWED_DOCUMENT_FILE_EXTENSIONS:
        raise ValueError("Document file must be PDF, DOC, DOCX, or TXT.")

    return filename


def store_document_file(
    session: Session,
    document_id: str,
    *,
    filename: str,
    mime_type: str,
    content: bytes,
) -> DocumentResponse:
    document = session.get(ApplicationDocument, document_id)
    if document is None:
        raise LookupError("Application document was not found.")

    require_writable_application(session, document.application_id)

    safe_filename = _safe_document_filename(filename)

    if not content:
        raise ValueError("Document file is empty.")

    if len(content) > MAX_DOCUMENT_FILE_BYTES:
        raise ValueError("Document file exceeds the 10 MB limit.")

    normalized_mime = mime_type.strip() or "application/octet-stream"
    if len(normalized_mime) > 240:
        raise ValueError("Document MIME type is too long.")

    digest = hashlib.sha256(content).hexdigest()

    document.stored_filename = safe_filename
    document.mime_type = normalized_mime
    document.file_size = len(content)
    document.file_sha256 = digest
    document.file_content = content
    document.updated_at = utc_now()

    session.add(
        _event(
            document.application_id,
            "document_file_stored",
            (f"{document.title}: {safe_filename}; {len(content)} bytes; sha256 {digest}."),
        )
    )
    session.commit()
    return _document_response(document)


def get_document_file(
    session: Session,
    document_id: str,
) -> tuple[str, str, bytes]:
    document = session.get(ApplicationDocument, document_id)
    if document is None:
        raise LookupError("Application document was not found.")

    if document.file_content is None or not document.stored_filename:
        raise LookupError("Application document file was not found.")

    return (
        document.stored_filename,
        document.mime_type or "application/octet-stream",
        document.file_content,
    )
