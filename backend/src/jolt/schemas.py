from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

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
    recommendation: str
    confidence: str
    ranking_score: int
    reasons: list[str]
    profile_version_id: str
    engine_version: str


class LinkedInFixtureCaptureRequest(BaseModel):
    listing_html: str = Field(min_length=1)
    detail_html_by_job_id: dict[str, str]
    search_url: str = ""
    page_number: int = Field(default=1, ge=1)


class LinkedInLiveCaptureItemRequest(BaseModel):
    source_job_id: str = Field(min_length=1)
    source_url: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    identity_verified: bool
    verification_reason: str = ""


class LinkedInLiveCaptureRequest(BaseModel):
    search_url: str = ""
    items: list[LinkedInLiveCaptureItemRequest] = Field(min_length=1, max_length=50)
    requested_item_limit: int | None = Field(default=None, ge=1, le=50)
    stop_reason: str = Field(default="", max_length=80)


class CaptureItemResponse(BaseModel):
    capture_item_id: str
    source_job_id: str
    source_url: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    detail_status: str
    verification_reasons: list[str]
    source_document_id: str | None = None
    posting_id: str | None = None
    identity_status: str | None = None
    artifact_id: str | None = None
    artifact_hash: str | None = None


class CapturePageResponse(BaseModel):
    page_number: int
    visible_job_ids: list[str]
    next_control_present: bool
    next_control_enabled: bool


class CaptureRunSummary(BaseModel):
    capture_run_id: str
    source: str
    mode: str
    status: str
    search_url: str
    warnings: list[str]
    requested_item_limit: int | None = None
    observed_item_count: int = 0
    stop_reason: str = ""
    started_at: str
    completed_at: str | None
    total_items: int
    verified_items: int
    rejected_items: int

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def normalize_utc_timestamp(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value)
        else:
            return value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat()


class CaptureRunResponse(CaptureRunSummary):
    pages: list[CapturePageResponse]
    items: list[CaptureItemResponse]


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


class ApplicationReadinessSummary(BaseModel):
    report_id: str
    profile_version_id: str
    engine_version: str
    priority: str
    readiness_score: int
    evidence_matches: list[str] = Field(default_factory=list)
    credibility_warnings: list[str] = Field(default_factory=list)
    cv_tailoring_points: list[str] = Field(default_factory=list)
    talking_points: list[str] = Field(default_factory=list)
    interview_questions: list[str] = Field(default_factory=list)
    revision_topics: list[str] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)


class OpportunitySummary(BaseModel):
    posting_id: str
    evaluation_id: str = ""
    source_url: str = ""
    title: str
    company: str
    location: str
    recommendation: str
    proposed_decision: str = "needs_more_information"
    confidence: str = ""
    ranking_score: int
    fit_summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    dimensions: dict[str, int] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    profile_version_id: str = ""
    engine_version: str = ""
    readiness: ApplicationReadinessSummary | None = None
    review_decision: str | None = None
    application_id: str | None = None
    application_status: str | None = None
    outcome_type: str | None = None
