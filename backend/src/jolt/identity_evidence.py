from __future__ import annotations

from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from jolt.database import Base, Posting, SourceDocument, utc_now


class PostingEvidence(Base):
    __tablename__ = "posting_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    posting_id: Mapped[str] = mapped_column(ForeignKey("postings.id"), nullable=False, index=True)
    source_document_id: Mapped[str] = mapped_column(
        ForeignKey("source_documents.id"), nullable=False, unique=True, index=True
    )
    identity_status: Mapped[str] = mapped_column(String(40), nullable=False)
    match_basis: Mapped[str] = mapped_column(String(40), nullable=False)
    linked_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)


def stage_posting_evidence(
    session: Session,
    *,
    posting_id: str,
    source_document_id: str,
    identity_status: str,
    match_basis: str,
) -> PostingEvidence:
    evidence = PostingEvidence(
        id=str(uuid4()),
        posting_id=posting_id,
        source_document_id=source_document_id,
        identity_status=identity_status,
        match_basis=match_basis,
        linked_at=utc_now(),
    )
    session.add(evidence)
    return evidence


def ensure_original_posting_evidence(session: Session, posting: Posting) -> None:
    existing = session.scalar(
        select(PostingEvidence).where(
            PostingEvidence.source_document_id == posting.source_document_id
        )
    )
    if existing is None:
        stage_posting_evidence(
            session,
            posting_id=posting.id,
            source_document_id=posting.source_document_id,
            identity_status="original",
            match_basis="canonical_posting",
        )


def posting_evidence_payloads(session: Session, posting: Posting) -> list[dict[str, object]]:
    ensure_original_posting_evidence(session, posting)
    rows = session.execute(
        select(PostingEvidence, SourceDocument)
        .join(SourceDocument, SourceDocument.id == PostingEvidence.source_document_id)
        .where(PostingEvidence.posting_id == posting.id)
        .order_by(SourceDocument.captured_at)
    ).all()
    return [
        {
            "source_document_id": evidence.source_document_id,
            "source_type": source.source_type,
            "source_url": source.source_url,
            "identity_status": evidence.identity_status,
            "match_basis": evidence.match_basis,
            "captured_at": source.captured_at.isoformat(),
        }
        for evidence, source in rows
    ]
