"""Read-only, conservative review candidates for offers on different portals."""

from __future__ import annotations

from collections import defaultdict
from typing import cast

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import ConfirmedDuplicateLink, Posting, PostingSourceIdentity
from jolt.semantic_duplicates import normalize_duplicate_text
from jolt.sources.duplicate_assessment import assess_duplicate
from jolt.sources.normalized_offer import NormalizedJobOffer, Portal


class CrossPortalDuplicateCandidate(BaseModel):
    first_posting_id: str
    second_posting_id: str
    first_portal: Portal
    second_portal: Portal
    first_url: str
    second_url: str
    title: str
    company: str
    decision: str
    reason: str


def list_cross_portal_duplicate_candidates(
    session: Session, *, limit: int = 100
) -> list[CrossPortalDuplicateCandidate]:
    """Compare verified portal identities without altering or merging any Posting."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    rows = session.execute(
        select(PostingSourceIdentity, Posting)
        .join(Posting, Posting.id == PostingSourceIdentity.posting_id)
        .order_by(PostingSourceIdentity.portal, PostingSourceIdentity.source_job_id)
    ).all()
    buckets: dict[tuple[str, str], list[tuple[PostingSourceIdentity, Posting]]] = defaultdict(list)
    for source, posting in rows:
        key = (
            normalize_duplicate_text(posting.company),
            normalize_duplicate_text(posting.title),
        )
        if all(key):
            buckets[key].append((source, posting))

    confirmed = {
        (link.first_posting_id, link.second_posting_id)
        for link in session.scalars(select(ConfirmedDuplicateLink)).all()
    }
    results: list[CrossPortalDuplicateCandidate] = []
    compared: set[tuple[str, str]] = set()
    for bucket in buckets.values():
        for i, (first_source, first_posting) in enumerate(bucket):
            for second_source, second_posting in bucket[i + 1 :]:
                if first_source.portal == second_source.portal:
                    continue
                if first_posting.id == second_posting.id:
                    continue
                pair = (
                    min(first_posting.id, second_posting.id),
                    max(first_posting.id, second_posting.id),
                )
                if pair in compared or pair in confirmed:
                    continue
                compared.add(pair)
                first = NormalizedJobOffer(
                    portal=cast(Portal, first_source.portal),
                    source_job_id=first_source.source_job_id,
                    source_url=first_source.source_url,
                    title=first_posting.title,
                    company=first_posting.company,
                    location=first_posting.location,
                    description=first_posting.description,
                    identity_verified=True,
                    detail_verified=True,
                )
                second = NormalizedJobOffer(
                    portal=cast(Portal, second_source.portal),
                    source_job_id=second_source.source_job_id,
                    source_url=second_source.source_url,
                    title=second_posting.title,
                    company=second_posting.company,
                    location=second_posting.location,
                    description=second_posting.description,
                    identity_verified=True,
                    detail_verified=True,
                )
                assessment = assess_duplicate(first, second)
                if assessment.decision not in {"probable_same_vacancy", "needs_review"}:
                    continue
                results.append(
                    CrossPortalDuplicateCandidate(
                        first_posting_id=first_posting.id,
                        second_posting_id=second_posting.id,
                        first_portal=first.portal,
                        second_portal=second.portal,
                        first_url=first.source_url,
                        second_url=second.source_url,
                        title=first.title,
                        company=first.company,
                        decision=assessment.decision,
                        reason=assessment.reason,
                    )
                )
                if len(results) >= limit:
                    return results
    return results
