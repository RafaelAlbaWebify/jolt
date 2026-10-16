"""Explicit, non-destructive confirmation of a cross-portal vacancy match."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from jolt.database import ConfirmedDuplicateLink, Posting, PostingSourceIdentity, utc_now
from jolt.sources.duplicate_assessment import assess_duplicate
from jolt.sources.normalized_offer import NormalizedJobOffer, Portal

Confirmation = Literal["CONFIRM SAME VACANCY"]


class ConfirmDuplicateRequest(BaseModel):
    first_posting_id: str
    second_posting_id: str
    confirmation: Confirmation


class ConfirmDuplicateResponse(BaseModel):
    first_posting_id: str
    second_posting_id: str
    status: str
    reason: str


def confirm_duplicate(
    session: Session, request: ConfirmDuplicateRequest
) -> ConfirmDuplicateResponse:
    """Link only reviewable offers; never move sources, reviews, or applications."""
    if request.first_posting_id == request.second_posting_id:
        raise ValueError("A posting cannot be linked to itself")

    first_id, second_id = sorted((request.first_posting_id, request.second_posting_id))
    existing = session.scalar(
        select(ConfirmedDuplicateLink).where(
            ConfirmedDuplicateLink.first_posting_id == first_id,
            ConfirmedDuplicateLink.second_posting_id == second_id,
        )
    )
    if existing is not None:
        return ConfirmDuplicateResponse(
            first_posting_id=first_id,
            second_posting_id=second_id,
            status="already_confirmed",
            reason=existing.reason,
        )

    postings = {
        posting.id: posting
        for posting in session.scalars(select(Posting).where(Posting.id.in_((first_id, second_id))))
    }
    if len(postings) != 2:
        raise ValueError("Both postings must exist")

    identities = session.scalars(
        select(PostingSourceIdentity).where(
            or_(
                PostingSourceIdentity.posting_id == first_id,
                PostingSourceIdentity.posting_id == second_id,
            )
        )
    ).all()
    sources: dict[str, list[PostingSourceIdentity]] = {first_id: [], second_id: []}
    for identity in identities:
        sources[identity.posting_id].append(identity)
    if not sources[first_id] or not sources[second_id]:
        raise ValueError("Both postings require verified portal source identities")

    best_reason: str | None = None
    for left_source in sources[first_id]:
        for right_source in sources[second_id]:
            if left_source.portal == right_source.portal:
                continue
            left_post = postings[first_id]
            right_post = postings[second_id]
            left = NormalizedJobOffer(
                portal=left_source.portal,
                source_job_id=left_source.source_job_id,
                source_url=left_source.source_url,
                title=left_post.title,
                company=left_post.company,
                location=left_post.location,
                description=left_post.description,
                identity_verified=True,
                detail_verified=True,
            )
            right = NormalizedJobOffer(
                portal=right_source.portal,
                source_job_id=right_source.source_job_id,
                source_url=right_source.source_url,
                title=right_post.title,
                company=right_post.company,
                location=right_post.location,
                description=right_post.description,
                identity_verified=True,
                detail_verified=True,
            )
            result = assess_duplicate(left, right)
            if result.decision == "probable_same_vacancy":
                best_reason = result.reason
                break
        if best_reason is not None:
            break
    if best_reason is None:
        raise ValueError("Vacancies are not eligible for confirmation; review evidence manually")

    link = ConfirmedDuplicateLink(
        id=str(uuid4()),
        first_posting_id=first_id,
        second_posting_id=second_id,
        confirmed_at=utc_now(),
        reason=best_reason,
    )
    session.add(link)
    session.commit()
    return ConfirmDuplicateResponse(
        first_posting_id=first_id,
        second_posting_id=second_id,
        status="confirmed",
        reason=best_reason,
    )
