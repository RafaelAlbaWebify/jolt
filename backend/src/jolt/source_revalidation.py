from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import AIReview, Application, ReviewDecision, utc_now
from jolt.errors import JoltNotFoundError

WorkModel = Literal["remote", "hybrid", "on_site", "unknown"]
AuthoritativeSource = Literal[
    "official_ats",
    "official_careers",
    "company_site",
    "linkedin",
    "unknown",
]
RemoteStatus = Literal[
    "confirmed_remote",
    "not_confirmed_remote",
    "not_remote",
    "unknown",
]
LocationVerificationStatus = Literal[
    "verified",
    "conflict",
    "unverified",
    "not_found",
]
SourceConfidence = Literal["high", "medium", "low", "unknown"]
Resolution = Literal["preserve", "hold_verify_location", "reject_location"]


class SourceRevalidationItem(BaseModel):
    ai_review_id: str
    posting_id: str
    source_conflict: bool
    linkedin_work_model: WorkModel
    official_work_model: WorkModel
    authoritative_source: AuthoritativeSource
    official_source_url: str = ""
    remote_status: RemoteStatus
    location_verification_status: LocationVerificationStatus
    source_confidence: SourceConfidence
    location_evidence: list[str] = Field(default_factory=list)
    resolution: Resolution = "preserve"
    reason: str = ""

    @model_validator(mode="after")
    def validate_resolution(self) -> SourceRevalidationItem:
        if self.source_conflict and self.location_verification_status != "conflict":
            raise ValueError("source_conflict requires location_verification_status=conflict")
        if (
            self.official_work_model in {"hybrid", "on_site"}
            and self.remote_status == "confirmed_remote"
        ):
            raise ValueError("Official hybrid/on-site evidence cannot be confirmed_remote")
        if self.resolution == "preserve" and self.source_conflict:
            raise ValueError("A source conflict cannot use resolution=preserve")
        if self.resolution == "reject_location" and self.location_verification_status != "verified":
            raise ValueError("reject_location requires verified authoritative location evidence")
        return self


class SourceRevalidationImportRequest(BaseModel):
    contract_type: Literal["jolt_source_revalidation"] = "jolt_source_revalidation"
    contract_version: Literal["1.0"] = "1.0"
    review_version: str
    items: list[SourceRevalidationItem]


class SourceRevalidationImportResponse(BaseModel):
    received_count: int
    updated_count: int
    protected_human_state_count: int


def import_source_revalidation(
    session: Session,
    request: SourceRevalidationImportRequest,
) -> SourceRevalidationImportResponse:
    ids = [item.ai_review_id for item in request.items]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate ai_review_id in source revalidation payload")

    reviews = {
        review.id: review
        for review in session.scalars(select(AIReview).where(AIReview.id.in_(ids))).all()
    }

    posting_ids = {item.posting_id for item in request.items}
    protected_human_state = set(
        session.scalars(
            select(ReviewDecision.posting_id).where(ReviewDecision.posting_id.in_(posting_ids))
        ).all()
    ) | set(
        session.scalars(
            select(Application.posting_id).where(Application.posting_id.in_(posting_ids))
        ).all()
    )

    updated_count = 0
    imported_at = utc_now()

    for item in request.items:
        review = reviews.get(item.ai_review_id)
        if review is None:
            raise JoltNotFoundError(f"AI review not found: {item.ai_review_id}")
        if review.posting_id != item.posting_id:
            raise ValueError(
                f"AI review {item.ai_review_id} does not belong to posting {item.posting_id}"
            )

        if (
            item.linkedin_work_model == "remote"
            and item.resolution == "preserve"
            and (
                item.remote_status != "confirmed_remote"
                or item.location_verification_status != "verified"
                or item.authoritative_source
                not in {"official_ats", "official_careers", "company_site"}
                or item.official_work_model != "remote"
                or item.source_conflict
            )
        ):
            raise ValueError(
                "Preserving a positive LinkedIn-Remote review requires verified official remote evidence"
            )

        review.source_conflict = item.source_conflict
        review.linkedin_work_model = item.linkedin_work_model
        review.official_work_model = item.official_work_model
        review.authoritative_source = item.authoritative_source
        review.official_source_url = item.official_source_url
        review.remote_status = item.remote_status
        review.location_verification_status = item.location_verification_status
        review.source_confidence = item.source_confidence
        if item.location_evidence:
            review.location_evidence_json = json.dumps(
                item.location_evidence,
                ensure_ascii=False,
            )
        if item.reason and item.resolution != "preserve":
            review.decision_reason = item.reason

        if item.resolution == "hold_verify_location":
            review.decision = "conditional"
            review.geography_status = "conditional"
            review.location_eligibility = "conditional"
            # Preserve technical fit and Stage-2 evidence. The point of this state
            # is that the vacancy may still be worth pursuing once geography is resolved.
        elif item.resolution == "reject_location":
            review.decision = "reject"
            review.geography_status = "ineligible"
            review.location_eligibility = "ineligible"
            review.hardline_status = "REJECT"
            review.fit_analysis_allowed = False
            review.technical_fit = None

        review.review_version = request.review_version
        review.contract_version = "1.2"
        review.imported_at = imported_at
        updated_count += 1

    session.commit()
    return SourceRevalidationImportResponse(
        received_count=len(request.items),
        updated_count=updated_count,
        protected_human_state_count=len(protected_human_state),
    )
