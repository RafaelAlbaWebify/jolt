from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import AIReview, Application, ReviewDecision, utc_now
from jolt.errors import JoltNotFoundError

HardlineType = Literal[
    "language",
    "clearance",
    "certification",
    "employment",
    "experience",
    "work_authorization",
    "schedule",
    "other",
]
Resolution = Literal["preserve", "hold", "reject"]


class HardlineRevalidationItem(BaseModel):
    ai_review_id: str
    posting_id: str
    hardline_type: HardlineType
    resolution: Resolution
    evidence: list[str] = Field(default_factory=list)
    reason: str

    @model_validator(mode="after")
    def validate_item(self) -> HardlineRevalidationItem:
        if self.resolution != "preserve" and not self.evidence:
            raise ValueError("hold/reject hardline revalidation requires evidence")
        return self


class HardlineRevalidationImportRequest(BaseModel):
    contract_type: Literal["jolt_hardline_revalidation"] = "jolt_hardline_revalidation"
    contract_version: Literal["1.0"] = "1.0"
    review_version: str
    items: list[HardlineRevalidationItem]


class HardlineRevalidationImportResponse(BaseModel):
    received_count: int
    updated_count: int
    protected_human_state_count: int


def import_hardline_revalidation(
    session: Session,
    request: HardlineRevalidationImportRequest,
) -> HardlineRevalidationImportResponse:
    ids = [item.ai_review_id for item in request.items]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate ai_review_id in hardline revalidation payload")

    reviews = {
        review.id: review
        for review in session.scalars(select(AIReview).where(AIReview.id.in_(ids))).all()
    }

    posting_ids = {item.posting_id for item in request.items}
    protected_human_state = set(
        session.scalars(
            select(ReviewDecision.posting_id).where(
                ReviewDecision.posting_id.in_(posting_ids)
            )
        ).all()
    ) | set(
        session.scalars(
            select(Application.posting_id).where(Application.posting_id.in_(posting_ids))
        ).all()
    )

    imported_at = utc_now()
    updated_count = 0

    for item in request.items:
        review = reviews.get(item.ai_review_id)
        if review is None:
            raise JoltNotFoundError(f"AI review not found: {item.ai_review_id}")
        if review.posting_id != item.posting_id:
            raise ValueError(
                f"AI review {item.ai_review_id} does not belong to posting {item.posting_id}"
            )

        if item.resolution == "preserve":
            continue

        review.hardline_reasons_json = json.dumps(item.evidence, ensure_ascii=False)
        review.decision_reason = item.reason
        review.review_version = request.review_version
        review.contract_version = "1.2"
        review.imported_at = imported_at

        if item.hardline_type == "language":
            review.language_status = "blocked" if item.resolution == "reject" else "conditional"
        elif item.hardline_type in {"clearance", "certification"}:
            review.clearance_status = (
                "blocked" if item.resolution == "reject" else "conditional"
            )
        elif item.hardline_type in {"employment", "work_authorization"}:
            if item.resolution == "reject":
                review.geography_status = "ineligible"
                review.location_eligibility = "ineligible"
            else:
                review.geography_status = "conditional"
                review.location_eligibility = "conditional"

        if item.resolution == "reject":
            review.decision = "reject"
            review.hardline_status = "REJECT"
            review.fit_analysis_allowed = False
            review.technical_fit = None
        else:
            review.decision = "conditional"
            review.hardline_status = "MANUAL_REVIEW"
            review.fit_analysis_allowed = False
            review.technical_fit = None

        updated_count += 1

    session.commit()
    return HardlineRevalidationImportResponse(
        received_count=len(request.items),
        updated_count=updated_count,
        protected_human_state_count=len(protected_human_state),
    )
