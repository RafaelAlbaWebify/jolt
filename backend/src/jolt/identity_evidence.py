from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Posting, SourceDocument
from jolt.workflow import normalize_url


def opportunity_identity_evidence(session: Session, posting_id: str) -> dict[str, object]:
    posting = session.get(Posting, posting_id)
    if posting is None:
        raise LookupError("Posting was not found.")

    original = session.get(SourceDocument, posting.source_document_id)
    if original is None:
        raise RuntimeError("Posting source document was not found.")

    documents = session.scalars(select(SourceDocument).order_by(SourceDocument.captured_at)).all()
    evidence: list[dict[str, object]] = []
    seen: set[str] = set()

    for document in documents:
        match_basis = ""
        normalized_source_url = normalize_url(document.source_url)
        if posting.canonical_url and normalized_source_url == posting.canonical_url:
            match_basis = "canonical_url"
        elif document.content_hash == original.content_hash:
            match_basis = "content_hash"
        if not match_basis or document.id in seen:
            continue
        seen.add(document.id)
        evidence.append(
            {
                "source_document_id": document.id,
                "source_type": document.source_type,
                "source_url": document.source_url,
                "identity_status": (
                    "original" if document.id == posting.source_document_id else "confirmed_duplicate"
                ),
                "match_basis": match_basis,
                "captured_at": document.captured_at.isoformat(),
            }
        )

    duplicate_count = sum(item["identity_status"] == "confirmed_duplicate" for item in evidence)
    return {
        "posting_id": posting.id,
        "canonical_url": posting.canonical_url,
        "identity_status": posting.identity_status,
        "evidence_count": len(evidence),
        "duplicate_evidence_count": duplicate_count,
        "evidence": evidence,
    }
