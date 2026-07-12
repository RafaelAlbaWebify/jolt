from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReviewChoice = Literal["pursue", "consider", "defer", "reject", "needs_more_information"]
Recommendation = Literal["pursue", "consider", "reject"]
ApplicationStatus = Literal[
    "preparing",
    "submitted",
    "acknowledged",
    "recruiter_screen",
    "technical_interview",
    "hiring_manager_interview",
    "final_interview",
    "offer",
    "rejected",
    "withdrawn",
    "no_response",
    "closed",
]
OutcomeType = Literal[
    "rejected_by_employer",
    "withdrawn_by_user",
    "no_response",
    "offer_declined",
    "offer_accepted",
    "role_closed",
]


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


class ApplicationCreateRequest(BaseModel):
    application_url: str = ""
    resume_used: str = ""
    notes: str = ""


class ApplicationTransitionRequest(BaseModel):
    status: ApplicationStatus
    notes: str = ""


class OutcomeRequest(BaseModel):
    outcome_type: OutcomeType
    reason_code: str = ""
    notes: str = ""


class ApplicationEventResponse(BaseModel):
    event_id: str
    event_type: str
    from_status: str
    to_status: str
    notes: str
    occurred_at: str


class ApplicationResponse(BaseModel):
    application_id: str
    posting_id: str
    status: str
    application_url: str
    resume_used: str
    notes: str
    outcome_type: str | None = None
    events: list[ApplicationEventResponse]


class OpportunitySummary(BaseModel):
    posting_id: str
    title: str
    company: str
    location: str
    recommendation: Recommendation
    ranking_score: int
    review_decision: ReviewChoice | None = None
    application_id: str | None = None
    application_status: str | None = None
    outcome_type: str | None = None
