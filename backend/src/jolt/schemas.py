from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReviewChoice = Literal["pursue", "consider", "defer", "reject", "needs_more_information"]
Recommendation = Literal["pursue", "consider", "reject"]


class ManualIntakeRequest(BaseModel):
    raw_text: str = Field(min_length=1)
    source_url: str = ""
    source_type: str = "manual"


class IntakeResponse(BaseModel):
    source_document_id: str
    posting_id: str
    evaluation_id: str
    identity_status: str
    duplicate_of_posting_id: str | None = None
    title: str
    company: str
    location: str
    recommendation: Recommendation
    confidence: str
    ranking_score: int
    reasons: list[str]
    profile_version_id: str
    engine_version: str


class ReviewRequest(BaseModel):
    evaluation_id: str
    decision: ReviewChoice
    reason_code: str = ""
    notes: str = ""


class ReviewResponse(BaseModel):
    review_id: str
    posting_id: str
    evaluation_id: str
    decision: ReviewChoice
    evaluation_overridden: bool


class OpportunitySummary(BaseModel):
    posting_id: str
    title: str
    company: str
    location: str
    recommendation: Recommendation
    ranking_score: int
    review_decision: ReviewChoice | None = None
