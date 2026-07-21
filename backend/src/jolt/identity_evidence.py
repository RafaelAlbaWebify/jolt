from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Posting, SourceDocument
from jolt.workflow import normalize_url


def _evidence_for_posting(
    posting: Posting,
    *,
    documents_by_id: dict[str, SourceDocument],
    documents_by_url: dict[str, list[SourceDocument]],
    documents_by_hash: dict[str, list[SourceDocument]],
) -> dict[str, object]:
    original = documents_by_id.get(posting.source_document_id)
    if original is None:
        raise RuntimeError("Posting source document was not found.")

    candidates = [
        *documents_by_url.get(posting.canonical_url, []),
        *documents_by_hash.get(original.content_hash, []),
    ]
    evidence: list[dict[str, object]] = []
    seen: set[str] = set()

    for document in sorted(candidates, key=lambda item: item.captured_at):
        if document.id in seen:
            continue
        match_basis = ""
        normalized_source_url = normalize_url(document.source_url)
        if posting.canonical_url and normalized_source_url == posting.canonical_url:
            match_basis = "canonical_url"
        elif document.content_hash == original.content_hash:
            match_basis = "content_hash"
        if not match_basis:
            continue
        seen.add(document.id)
        evidence.append(
            {
                "source_document_id": document.id,
                "source_type": document.source_type,
                "source_url": document.source_url,
                "identity_status": (
                    "original"
                    if document.id == posting.source_document_id
                    else "confirmed_duplicate"
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


def list_identity_evidence(session: Session) -> list[dict[str, object]]:
    postings = session.scalars(select(Posting).order_by(Posting.created_at, Posting.id)).all()
    documents = session.scalars(select(SourceDocument).order_by(SourceDocument.captured_at)).all()

    documents_by_id = {document.id: document for document in documents}
    documents_by_url: dict[str, list[SourceDocument]] = defaultdict(list)
    documents_by_hash: dict[str, list[SourceDocument]] = defaultdict(list)
    for document in documents:
        normalized_source_url = normalize_url(document.source_url)
        if normalized_source_url:
            documents_by_url[normalized_source_url].append(document)
        documents_by_hash[document.content_hash].append(document)

    return [
        {
            "opportunity": {
                "posting_id": posting.id,
                "title": posting.title,
                "company": posting.company,
                "location": posting.location,
            },
            "evidence": _evidence_for_posting(
                posting,
                documents_by_id=documents_by_id,
                documents_by_url=documents_by_url,
                documents_by_hash=documents_by_hash,
            ),
        }
        for posting in postings
    ]


def opportunity_identity_evidence(session: Session, posting_id: str) -> dict[str, object]:
    posting = session.get(Posting, posting_id)
    if posting is None:
        raise LookupError("Posting was not found.")

    documents = session.scalars(select(SourceDocument).order_by(SourceDocument.captured_at)).all()
    documents_by_id = {document.id: document for document in documents}
    documents_by_url: dict[str, list[SourceDocument]] = defaultdict(list)
    documents_by_hash: dict[str, list[SourceDocument]] = defaultdict(list)
    for document in documents:
        normalized_source_url = normalize_url(document.source_url)
        if normalized_source_url:
            documents_by_url[normalized_source_url].append(document)
        documents_by_hash[document.content_hash].append(document)

    return _evidence_for_posting(
        posting,
        documents_by_id=documents_by_id,
        documents_by_url=documents_by_url,
        documents_by_hash=documents_by_hash,
    )
