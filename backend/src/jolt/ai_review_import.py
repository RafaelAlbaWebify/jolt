from __future__ import annotations

import json
from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import (
    AIReview,
    Application,
    CaptureItem,
    CaptureRun,
    Posting,
    ReviewDecision,
    SourceDocument,
    utc_now,
)
from jolt.errors import JoltNotFoundError
from jolt.hardline_evidence import analyze_location_evidence
from jolt.job_search_preferences import load_job_search_preferences
from jolt.language_hardline import analyze_language_evidence
from jolt.preference_aware_evaluation import sanitize_capture_text

AIReviewDecision = Literal[
    "strong_pursue",
    "pursue",
    "conditional",
    "reject",
]

HardlineStatus = Literal["PASS", "REJECT", "MANUAL_REVIEW"]

GeographyStatus = Literal[
    "eligible",
    "conditional",
    "ineligible",
    "unknown",
]

LocationEligibility = Literal[
    "eligible",
    "conditional",
    "ineligible",
    "unknown",
]

ClearanceStatus = Literal[
    "clear",
    "conditional",
    "blocked",
    "unknown",
]

LanguageStatus = Literal[
    "clear",
    "conditional",
    "blocked",
    "unknown",
]

RequirementClassification = Literal["required", "preferred", "nice_to_have"]
RequirementResult = Literal["met", "partial", "unmet", "unknown"]
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


class MandatoryRequirementResult(BaseModel):
    requirement: str = Field(min_length=1)
    source_text: str = Field(min_length=1)
    classification: RequirementClassification
    candidate_evidence: str = ""
    result: RequirementResult
    hardline: bool


class AIReviewJob(BaseModel):
    posting_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)

    decision: AIReviewDecision | None = None
    priority_score: int = Field(ge=0, le=100)
    geography_status: GeographyStatus
    clearance_status: ClearanceStatus
    language_status: LanguageStatus
    technical_fit: int | None = Field(default=None, ge=0, le=100)

    hardline_status: HardlineStatus = "PASS"
    hardline_reasons: list[str] = Field(default_factory=list)
    location_eligibility: LocationEligibility = "unknown"
    location_evidence: list[str] = Field(default_factory=list)
    mandatory_requirements: list[MandatoryRequirementResult] = Field(default_factory=list)
    mandatory_requirement_results: list[MandatoryRequirementResult] = Field(default_factory=list)
    employment_constraints: list[str] = Field(default_factory=list)
    fit_analysis_allowed: bool = True
    technical_fit_percent: int | None = Field(default=None, ge=0, le=100)
    final_decision: AIReviewDecision | None = None
    decision_reason: str = ""

    source_conflict: bool = False
    linkedin_work_model: WorkModel = "unknown"
    official_work_model: WorkModel = "unknown"
    authoritative_source: AuthoritativeSource = "unknown"
    official_source_url: str = ""
    remote_status: RemoteStatus = "unknown"
    location_verification_status: LocationVerificationStatus = "unverified"
    source_confidence: SourceConfidence = "unknown"

    duplicate_of_posting_id: str | None = None
    summary: str = ""
    reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_hardline_precedence(self) -> AIReviewJob:
        final_decision = self.final_decision or self.decision
        if final_decision is None:
            raise ValueError("A final decision is required")
        if self.decision is not None and final_decision != self.decision:
            raise ValueError("final_decision must match decision")
        self.decision = final_decision

        fit = self.technical_fit_percent
        if fit is None:
            fit = self.technical_fit
        elif self.technical_fit is not None and self.technical_fit != fit:
            raise ValueError("technical_fit and technical_fit_percent must match")

        if not self.fit_analysis_allowed and fit is not None:
            raise ValueError("technical fit must be null when fit_analysis_allowed is false")

        if self.hardline_status == "REJECT":
            if final_decision != "reject":
                raise ValueError("HARDLINE REJECT requires final_decision=reject")
            if self.fit_analysis_allowed:
                raise ValueError("HARDLINE REJECT must stop fit analysis")
            if fit is not None:
                raise ValueError("HARDLINE REJECT cannot carry a technical fit score")
            if not self.hardline_reasons:
                raise ValueError("HARDLINE REJECT requires at least one hardline reason")

        if self.hardline_status == "MANUAL_REVIEW":
            if self.fit_analysis_allowed:
                raise ValueError("MANUAL_REVIEW must stop before fit analysis")
            if fit is not None:
                raise ValueError("MANUAL_REVIEW cannot carry a technical fit score")
            if final_decision not in {"conditional", "reject"}:
                raise ValueError("MANUAL_REVIEW cannot recommend pursuing the job")

        if self.hardline_status == "PASS" and not self.fit_analysis_allowed:
            raise ValueError("PASS must allow Stage 2 fit analysis")

        if self.fit_analysis_allowed and fit is None:
            raise ValueError("Stage 2 requires technical_fit_percent")

        positive_decision = final_decision in {"strong_pursue", "pursue"}
        if positive_decision:
            if self.geography_status != "eligible":
                raise ValueError(
                    "Positive decisions require geography_status=eligible; unresolved geography caps the decision at conditional"
                )
            if self.clearance_status != "clear":
                raise ValueError(
                    "Positive decisions require clearance_status=clear; unresolved clearance caps the decision at conditional"
                )
            if self.language_status != "clear":
                raise ValueError(
                    "Positive decisions require language_status=clear; unresolved language caps the decision at conditional"
                )

        if self.geography_status == "ineligible" and final_decision != "reject":
            raise ValueError("Ineligible geography requires final_decision=reject")
        if self.clearance_status == "blocked" and final_decision != "reject":
            raise ValueError("Blocked clearance requires final_decision=reject")
        if self.language_status == "blocked" and final_decision != "reject":
            raise ValueError("Blocked language requires final_decision=reject")

        if self.duplicate_of_posting_id is not None and final_decision != "reject":
            raise ValueError("Duplicate postings must use final_decision=reject")

        self.final_decision = final_decision
        self.technical_fit_percent = fit
        self.technical_fit = fit
        return self


class AIReviewImportRequest(BaseModel):
    contract_type: Literal["jolt_ai_review"]
    contract_version: Literal["1.0", "1.1", "1.2"]
    capture_run_id: str = Field(min_length=1)
    review_source: Literal["chatgpt_source_first"]
    review_version: str = Field(min_length=1, max_length=80)
    reviewed_at: datetime
    jobs: list[AIReviewJob]

    @model_validator(mode="after")
    def require_current_review_fields(self) -> AIReviewImportRequest:
        if self.contract_version == "1.0":
            return self

        required_fields = {
            "hardline_status",
            "hardline_reasons",
            "location_eligibility",
            "location_evidence",
            "mandatory_requirements",
            "mandatory_requirement_results",
            "employment_constraints",
            "fit_analysis_allowed",
            "technical_fit_percent",
            "final_decision",
            "decision_reason",
        }
        source_fields = {
            "source_conflict",
            "linkedin_work_model",
            "official_work_model",
            "authoritative_source",
            "official_source_url",
            "remote_status",
            "location_verification_status",
            "source_confidence",
        }

        for job in self.jobs:
            missing = required_fields - job.model_fields_set
            if missing:
                raise ValueError(
                    f"AI review contract {self.contract_version} is missing hardline fields: "
                    + ", ".join(sorted(missing))
                )

            if self.contract_version == "1.2":
                missing_source = source_fields - job.model_fields_set
                if missing_source:
                    raise ValueError(
                        "AI review contract 1.2 is missing source-verification fields: "
                        + ", ".join(sorted(missing_source))
                    )
                self._validate_source_verification(job)

            if job.final_decision in {"strong_pursue", "pursue"}:
                if job.hardline_status != "PASS":
                    raise ValueError("Positive decisions require hardline_status=PASS")
                if job.location_eligibility != "eligible":
                    raise ValueError(
                        "Positive decisions require location_eligibility=eligible; unresolved employment territory caps the decision at conditional"
                    )

        return self

    @staticmethod
    def _validate_source_verification(job: AIReviewJob) -> None:
        official_sources = {"official_ats", "official_careers", "company_site"}
        known_linkedin = job.linkedin_work_model != "unknown"
        known_official = job.official_work_model != "unknown"

        if (
            known_linkedin
            and known_official
            and job.linkedin_work_model != job.official_work_model
            and not job.source_conflict
        ):
            raise ValueError(
                "LinkedIn and official work models diverge; source_conflict must be true"
            )

        if job.source_conflict:
            if job.location_verification_status != "conflict":
                raise ValueError("source_conflict requires location_verification_status=conflict")
            if job.location_eligibility == "eligible" or job.geography_status == "eligible":
                raise ValueError(
                    "A source conflict cannot be treated as verified eligible geography"
                )
            if job.final_decision in {"strong_pursue", "pursue"}:
                raise ValueError(
                    "A source conflict caps the decision at conditional until location/work model is verified"
                )

        if (
            job.official_work_model in {"hybrid", "on_site"}
            and job.remote_status == "confirmed_remote"
        ):
            raise ValueError(
                "Official hybrid/on-site evidence cannot be stored as confirmed_remote"
            )

        if job.linkedin_work_model == "remote" and job.final_decision in {
            "strong_pursue",
            "pursue",
        }:
            if job.remote_status != "confirmed_remote":
                raise ValueError(
                    "LinkedIn Remote cannot support a positive decision until remote_status=confirmed_remote"
                )
            if job.location_verification_status != "verified":
                raise ValueError(
                    "LinkedIn Remote cannot support a positive decision until official location verification is complete"
                )
            if job.authoritative_source not in official_sources:
                raise ValueError(
                    "LinkedIn Remote requires an official ATS/careers/company source before a positive decision"
                )
            if job.official_work_model != "remote":
                raise ValueError(
                    "LinkedIn Remote requires the authoritative official source to confirm remote work"
                )
            if job.source_conflict:
                raise ValueError(
                    "LinkedIn Remote with conflicting official evidence cannot produce a positive decision"
                )


class AIReviewImportResponse(BaseModel):
    capture_run_id: str
    received_count: int
    created_count: int
    updated_count: int
    protected_human_state_count: int


def _validate_exact_v11_capture_set(
    *,
    expected_posting_ids: set[str],
    returned_posting_ids: set[str],
) -> None:
    if returned_posting_ids == expected_posting_ids:
        return

    missing = sorted(expected_posting_ids - returned_posting_ids)
    unexpected = sorted(returned_posting_ids - expected_posting_ids)
    details: list[str] = []
    if missing:
        details.append("missing posting_id(s): " + ", ".join(missing))
    if unexpected:
        details.append("unexpected posting_id(s): " + ", ".join(unexpected))
    raise ValueError(
        "AI review contract 1.1 must return exactly one result for every posting in the capture; "
        + "; ".join(details)
    )


def _validate_capture_membership(
    session: Session,
    request: AIReviewImportRequest,
) -> None:
    capture = session.get(CaptureRun, request.capture_run_id)
    if capture is None:
        raise JoltNotFoundError(f"Capture run not found: {request.capture_run_id}")

    capture_items = list(
        session.scalars(
            select(CaptureItem).where(CaptureItem.capture_run_id == request.capture_run_id)
        ).all()
    )

    source_job_by_posting = {
        item.posting_id: item.source_job_id for item in capture_items if item.posting_id is not None
    }

    seen_postings: set[str] = set()

    for job in request.jobs:
        if job.posting_id in seen_postings:
            raise ValueError(f"Duplicate posting_id in AI review payload: {job.posting_id}")

        seen_postings.add(job.posting_id)

        expected_source_job_id = source_job_by_posting.get(job.posting_id)

        if expected_source_job_id is None:
            raise ValueError(
                f"AI review posting does not belong to the stated capture: {job.posting_id}"
            )

        if expected_source_job_id != job.source_job_id:
            raise ValueError(
                f"AI review source_job_id does not match capture evidence for {job.posting_id}"
            )

        posting = session.get(Posting, job.posting_id)
        if posting is None:
            raise ValueError(f"AI review references unknown posting: {job.posting_id}")

        if request.contract_version in {"1.1", "1.2"}:
            source_document = session.get(SourceDocument, posting.source_document_id)
            source_text = (
                source_document.raw_text if source_document is not None else posting.description
            )
            deterministic_location = analyze_location_evidence(
                location=posting.location,
                source_text=source_text,
            )
            if deterministic_location.hardline_reject and (
                job.hardline_status != "REJECT"
                or job.location_eligibility != "ineligible"
                or job.final_decision != "reject"
                or job.fit_analysis_allowed
                or job.technical_fit_percent is not None
            ):
                evidence = "; ".join(deterministic_location.negative_evidence)
                raise ValueError(
                    "AI review conflicts with deterministic source evidence for "
                    f"{job.posting_id}: {evidence}"
                )

            deterministic_language = analyze_language_evidence(
                source_text=sanitize_capture_text(source_text),
                preferences=load_job_search_preferences(),
            )
            if deterministic_language.hardline_reject and (
                job.hardline_status != "REJECT"
                or job.language_status != "blocked"
                or job.final_decision != "reject"
                or job.fit_analysis_allowed
                or job.technical_fit_percent is not None
            ):
                evidence = "; ".join(deterministic_language.reasons)
                raise ValueError(
                    "AI review conflicts with deterministic language evidence for "
                    f"{job.posting_id}: {evidence}"
                )
            if deterministic_language.manual_review and (
                job.hardline_status != "MANUAL_REVIEW"
                or job.language_status != "conditional"
                or job.final_decision not in {"conditional", "reject"}
                or job.fit_analysis_allowed
                or job.technical_fit_percent is not None
            ):
                evidence = "; ".join(deterministic_language.reasons)
                raise ValueError(
                    "AI review conflicts with ambiguous language evidence for "
                    f"{job.posting_id}: {evidence}"
                )

        if job.duplicate_of_posting_id is not None:
            if job.duplicate_of_posting_id == job.posting_id:
                raise ValueError("A posting cannot be marked as a duplicate of itself.")

            if session.get(Posting, job.duplicate_of_posting_id) is None:
                raise ValueError(
                    "duplicate_of_posting_id references unknown posting: "
                    f"{job.duplicate_of_posting_id}"
                )

    if request.contract_version == "1.1":
        _validate_exact_v11_capture_set(
            expected_posting_ids=set(source_job_by_posting),
            returned_posting_ids=seen_postings,
        )


def _requirement_json(items: list[MandatoryRequirementResult]) -> str:
    return json.dumps(
        [item.model_dump() for item in items],
        ensure_ascii=False,
    )


def import_ai_review(
    session: Session,
    request: AIReviewImportRequest,
) -> AIReviewImportResponse:
    """Persist external AI analysis without altering human/application state."""

    _validate_capture_membership(session, request)

    posting_ids = [job.posting_id for job in request.jobs]

    human_review_postings = set(
        session.scalars(
            select(ReviewDecision.posting_id).where(ReviewDecision.posting_id.in_(posting_ids))
        ).all()
    )

    application_postings = set(
        session.scalars(
            select(Application.posting_id).where(Application.posting_id.in_(posting_ids))
        ).all()
    )

    protected_human_state = human_review_postings | application_postings

    existing_reviews = {
        review.posting_id: review
        for review in session.scalars(
            select(AIReview).where(
                AIReview.capture_run_id == request.capture_run_id,
                AIReview.review_source == request.review_source,
                AIReview.posting_id.in_(posting_ids),
            )
        ).all()
    }

    created_count = 0
    updated_count = 0
    imported_at = utc_now()

    for job in request.jobs:
        review = existing_reviews.get(job.posting_id)
        posting = session.get(Posting, job.posting_id)
        source_document = (
            session.get(SourceDocument, posting.source_document_id) if posting is not None else None
        )
        source_text = (
            source_document.raw_text
            if source_document is not None
            else posting.description
            if posting is not None
            else ""
        )
        deterministic_language = analyze_language_evidence(
            source_text=sanitize_capture_text(source_text),
            preferences=load_job_search_preferences(),
        )
        stored_hardline_reasons = list(job.hardline_reasons)
        for reason in deterministic_language.reasons:
            if reason not in stored_hardline_reasons:
                stored_hardline_reasons.append(reason)

        values = {
            "source_job_id": job.source_job_id,
            "review_version": request.review_version,
            "contract_version": request.contract_version,
            "decision": job.final_decision or job.decision,
            "priority_score": job.priority_score,
            "geography_status": job.geography_status,
            "clearance_status": job.clearance_status,
            "language_status": job.language_status,
            "technical_fit": job.technical_fit_percent,
            "source_conflict": job.source_conflict,
            "linkedin_work_model": job.linkedin_work_model,
            "official_work_model": job.official_work_model,
            "authoritative_source": job.authoritative_source,
            "official_source_url": job.official_source_url,
            "remote_status": job.remote_status,
            "location_verification_status": job.location_verification_status,
            "source_confidence": job.source_confidence,
            "hardline_status": job.hardline_status,
            "hardline_reasons_json": json.dumps(stored_hardline_reasons, ensure_ascii=False),
            "location_eligibility": job.location_eligibility,
            "location_evidence_json": json.dumps(job.location_evidence, ensure_ascii=False),
            "mandatory_requirements_json": _requirement_json(job.mandatory_requirements),
            "mandatory_requirement_results_json": _requirement_json(
                job.mandatory_requirement_results
            ),
            "employment_constraints_json": json.dumps(
                job.employment_constraints, ensure_ascii=False
            ),
            "fit_analysis_allowed": job.fit_analysis_allowed,
            "decision_reason": job.decision_reason,
            "duplicate_of_posting_id": job.duplicate_of_posting_id,
            "summary": job.summary,
            "reasons_json": json.dumps(job.reasons, ensure_ascii=False),
            "reviewed_at": request.reviewed_at,
            "imported_at": imported_at,
        }

        if review is None:
            review = AIReview(
                id=str(uuid4()),
                capture_run_id=request.capture_run_id,
                posting_id=job.posting_id,
                review_source=request.review_source,
                **values,
            )
            session.add(review)
            created_count += 1
            continue

        for field_name, value in values.items():
            setattr(review, field_name, value)
        updated_count += 1

    session.commit()

    return AIReviewImportResponse(
        capture_run_id=request.capture_run_id,
        received_count=len(request.jobs),
        created_count=created_count,
        updated_count=updated_count,
        protected_human_state_count=len(protected_human_state),
    )
