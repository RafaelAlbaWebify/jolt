"""Safe registration of a portal's stable identity and all its observations.

A cross-portal probable match is not enough to reassign an existing identity.
Callers must explicitly choose an existing Posting when evidence is verified.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Posting, PostingSourceIdentity, SourceDocument, utc_now
from jolt.sources.normalized_offer import NormalizedJobOffer


def register_source_identity(
    session: Session,
    *,
    posting_id: str,
    offer: NormalizedJobOffer,
    source_document_id: str | None = None,
) -> PostingSourceIdentity:
    """Record an observed portal identity; never silently move it to another Posting."""
    if not offer.identity_verified:
        raise ValueError("Unverified portal identity cannot be registered")
    if session.get(Posting, posting_id) is None:
        raise ValueError("Target Posting not found")
    if source_document_id is not None and session.get(SourceDocument, source_document_id) is None:
        raise ValueError("Source document not found")
    current = session.scalar(
        select(PostingSourceIdentity).where(
            PostingSourceIdentity.portal == offer.portal,
            PostingSourceIdentity.source_job_id == offer.source_job_id,
        )
    )
    if current is not None:
        if current.posting_id != posting_id:
            raise ValueError(
                "Portal identity is already linked to another Posting; manual review required"
            )
        current.last_seen_at = utc_now()
        current.source_url = offer.source_url
        if source_document_id is not None:
            current.source_document_id = source_document_id
        session.flush()
        return current

    now = utc_now()
    current = PostingSourceIdentity(
        id=str(uuid4()),
        posting_id=posting_id,
        portal=offer.portal,
        source_job_id=offer.source_job_id,
        source_url=offer.source_url,
        first_seen_at=now,
        last_seen_at=now,
        source_document_id=source_document_id,
    )
    session.add(current)
    session.flush()
    return current


def list_posting_sources(session: Session, posting_id: str) -> list[PostingSourceIdentity]:
    return list(
        session.scalars(
            select(PostingSourceIdentity)
            .where(PostingSourceIdentity.posting_id == posting_id)
            .order_by(PostingSourceIdentity.portal, PostingSourceIdentity.source_job_id)
        ).all()
    )
