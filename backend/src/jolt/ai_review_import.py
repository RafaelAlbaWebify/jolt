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
    CompanyWatch,
    Posting,
    ReviewDecision,
    SourceDocument,
    utc_now,
)
from jolt.errors import JoltNotFoundError
from jolt.hardline_evidence import analyze_location_evidence

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

RemoteScope = Literal[
    "worldwide",
    "EMEA",
    "Europe",
    "Spain",
    "specific_country",
    "USA_only",
    "region_bound",
    "unknown",
]
WorkAuthorizationStatus = Literal["clear", "conditional", "blocked", "unknown"]
ConditionsStatus = Literal["clear", "conditional", "blocked", "unknown"]
OfficialSourceStatus = Literal["verified", "not_found", "unavailable", "not_checked"]
ExperienceEvidenceStatus = Literal[
    "confirmed_experience",
    "not_in_profile_yet",
    "unknown_ask_user",
    "confirmed_gap",
]
PreApplicationDecision = Literal[
    "APPLY_HIGH_FIT",
    "APPLY_MEDIUM_FIT",
    "SKIP_BY_LOCATION",
    "SKIP_BY_WORK_AUTHORIZATION",
    "SKIP_BY_SALARY_CONDITIONS",
    "SKIP_BY_TECHNICAL_FIT",
    "TARGET_COMPANY_WATCH",
    "NEEDS_USER_CONFIRMATION",
]


class MandatoryRequirementResult(BaseModel):
    requirement: str = Field(min_length=1)
    source_text: str = Field(min_length=1)
    classification: RequirementClassification
    candidate_evidence: str = ""
    candidate_evidence_status: ExperienceEvidenceStatus = "unknown_ask_user"
    result: RequirementResult
    hardline: bool


class ExperienceEvidence(BaseModel):
    skill: str = Field(min_length=1)
    source_requirement: str = ""
    status: ExperienceEvidenceStatus
    evidence: str = ""


class CVMasterRecommendation(BaseModel):
    language: Literal["en", "es"]
    family: Literal["application_support", "systems_automation"]
    master_label: str = Field(min_length=1)
    rationale: str = ""


class AIReviewJob(BaseModel):
    posting_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)

    decision: AIReviewDecision | None = None
    priority_score: int = Field(ge=0, le=100)
    geography_status: GeographyStatus
    clearance_status: ClearanceStatus
    language_status: LanguageStatus
    technical_fit: int | None = Field(default=None, ge=0, le=100)

    pre_application_decision: PreApplicationDecision | None = None
    remote_scope: RemoteScope = "unknown"
    work_authorization_status: WorkAuthorizationStatus = "unknown"
    conditions_status: ConditionsStatus = "unknown"
    official_source_status: OfficialSourceStatus = "not_checked"
    official_source_url: str = ""
    official_source_location: str = ""
    official_source_evidence: list[str] = Field(default_factory=list)
    experience_evidence: list[ExperienceEvidence] = Field(default_factory=list)
    questions_for_user: list[str] = Field(default_factory=list)
    company_watch: bool = False
    company_watch_reason: str = ""
    company_watch_role_patterns: list[str] = Field(default_factory=list)
    recommended_cv_master: CVMasterRecommendation | None = None
    recommended_certifications: list[str] = Field(default_factory=list, max_length=6)
    linkedin_skill_suggestions: list[str] = Field(default_factory=list)
    certification_inventory_complete: bool = False

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
            if not self.hardline_reasons:
                raise ValueError("HARDLINE REJECT requires at least one hardline reason")

        if self.hardline_status == "MANUAL_REVIEW":
            if final_decision not in {"conditional", "reject"}:
                raise ValueError("MANUAL_REVIEW cannot recommend pursuing the job")

        if self.fit_analysis_allowed and fit is None:
            raise ValueError("fit_analysis_allowed=true requires technical_fit_percent")

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


def _validate_v12_job(job: AIReviewJob) -> None:
    decision = job.pre_application_decision
    if decision is None:
        raise ValueError("AI review contract 1.2 requires pre_application_decision")

    if job.official_source_status == "verified":
        if not job.official_source_url.strip():
            raise ValueError("Verified official source requires official_source_url")
        if not job.official_source_evidence:
            raise ValueError("Verified official source requires official_source_evidence")

    if job.remote_scope == "USA_only" and decision != "SKIP_BY_LOCATION":
        raise ValueError("USA_only roles require SKIP_BY_LOCATION")

    if decision in {"APPLY_HIGH_FIT", "APPLY_MEDIUM_FIT"}:
        if job.final_decision not in {"strong_pursue", "pursue"}:
            raise ValueError("APPLY decisions require a pursue final_decision")
        if job.location_eligibility != "eligible" or job.geography_status != "eligible":
            raise ValueError("APPLY decisions require eligible geography")
        if job.work_authorization_status != "clear":
            raise ValueError("APPLY decisions require clear work authorization")
        if job.conditions_status == "blocked":
            raise ValueError("APPLY decisions cannot have blocked salary/conditions")
        if job.questions_for_user:
            raise ValueError("APPLY decisions cannot have unresolved user questions")

    if decision == "SKIP_BY_LOCATION":
        if job.final_decision != "reject":
            raise ValueError("SKIP_BY_LOCATION requires final_decision=reject")
        if job.location_eligibility != "ineligible" and job.geography_status != "ineligible":
            raise ValueError("SKIP_BY_LOCATION requires ineligible geography")

    if decision == "SKIP_BY_WORK_AUTHORIZATION":
        if job.final_decision != "reject" or job.work_authorization_status != "blocked":
            raise ValueError(
                "SKIP_BY_WORK_AUTHORIZATION requires reject and blocked work authorization"
            )

    if decision == "SKIP_BY_SALARY_CONDITIONS":
        if job.final_decision != "reject" or job.conditions_status != "blocked":
            raise ValueError(
                "SKIP_BY_SALARY_CONDITIONS requires reject and blocked conditions"
            )

    if decision == "SKIP_BY_TECHNICAL_FIT":
        if job.final_decision != "reject" or not job.fit_analysis_allowed:
            raise ValueError("SKIP_BY_TECHNICAL_FIT requires reject with technical fit analysis")
        confirmed_gaps = [
            item for item in job.experience_evidence if item.status == "confirmed_gap"
        ]
        if not confirmed_gaps:
            raise ValueError(
                "SKIP_BY_TECHNICAL_FIT requires at least one confirmed_gap evidence item"
            )

    if decision == "NEEDS_USER_CONFIRMATION":
        if job.final_decision != "conditional" or not job.questions_for_user:
            raise ValueError(
                "NEEDS_USER_CONFIRMATION requires conditional and questions_for_user"
            )

    for requirement in [
        *job.mandatory_requirements,
        *job.mandatory_requirement_results,
    ]:
        if requirement.candidate_evidence_status in {
            "confirmed_experience",
            "not_in_profile_yet",
        } and requirement.result == "unmet":
            raise ValueError(
                "Confirmed experience cannot be classified as an unmet requirement"
            )
        if requirement.candidate_evidence_status == "unknown_ask_user" and requirement.result == "unmet":
            raise ValueError(
                "Unknown experience must trigger user confirmation, not an unmet penalty"
            )

    if not job.certification_inventory_complete and job.recommended_certifications:
        raise ValueError(
            "Certification recommendations require the complete credential inventory"
        )

    if job.company_watch and not job.company_watch_reason.strip():
        raise ValueError("company_watch=true requires company_watch_reason")


class AIReviewImportRequest(BaseModel):
    contract_type: Literal["jolt_ai_review"]
    contract_version: Literal["1.0", "1.1", "1.2"]
    capture_run_id: str = Field(min_length=1)
    review_source: Literal["chatgpt_source_first"]
    review_version: str = Field(min_length=1, max_length=80)
    reviewed_at: datetime
    jobs: list[AIReviewJob]

    @model_validator(mode="after")
    def require_v11_hardline_fields(self) -> AIReviewImportRequest:
        if self.contract_version not in {"1.1", "1.2"}:
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
        if self.contract_version == "1.2":
            required_fields |= {
                "pre_application_decision",
                "remote_scope",
                "work_authorization_status",
                "conditions_status",
                "official_source_status",
                "official_source_url",
                "official_source_location",
                "official_source_evidence",
                "experience_evidence",
                "questions_for_user",
                "company_watch",
                "company_watch_reason",
                "company_watch_role_patterns",
                "recommended_cv_master",
                "recommended_certifications",
                "linkedin_skill_suggestions",
                "certification_inventory_complete",
            }

        for job in self.jobs:
            missing = required_fields - job.model_fields_set
            if missing:
                raise ValueError(
                    f"AI review contract {self.contract_version} is missing fields: "
                    + ", ".join(sorted(missing))
                )

            if self.contract_version == "1.1":
                if job.hardline_status in {"REJECT", "MANUAL_REVIEW"}:
                    if job.fit_analysis_allowed or job.technical_fit_percent is not None:
                        raise ValueError(
                            "AI review contract 1.1 requires REJECT/MANUAL_REVIEW to stop fit analysis"
                        )
                if job.hardline_status == "PASS" and not job.fit_analysis_allowed:
                    raise ValueError("AI review contract 1.1 PASS must allow fit analysis")

            if job.final_decision in {"strong_pursue", "pursue"}:
                if job.hardline_status != "PASS":
                    raise ValueError("Positive decisions require hardline_status=PASS")
                if job.location_eligibility != "eligible":
                    raise ValueError(
                        "Positive decisions require location_eligibility=eligible; unresolved employment territory caps the decision at conditional"
                    )

            if self.contract_version == "1.2":
                _validate_v12_job(job)

        return self


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

        if request.contract_version == "1.1":
            source_document = session.get(SourceDocument, posting.source_document_id)
            source_text = (
                source_document.raw_text if source_document is not None else posting.description
            )
            deterministic_location = analyze_location_evidence(
                location=posting.location,
                source_text=source_text,
            )
            if (
                deterministic_location.hardline_reject
                and job.official_source_status != "verified"
            ):
                if request.contract_version == "1.1":
                    conflict = (
                        job.hardline_status != "REJECT"
                        or job.location_eligibility != "ineligible"
                        or job.final_decision != "reject"
                        or job.fit_analysis_allowed
                        or job.technical_fit_percent is not None
                    )
                else:
                    conflict = (
                        job.hardline_status != "REJECT"
                        or job.location_eligibility != "ineligible"
                        or job.final_decision != "reject"
                        or job.pre_application_decision != "SKIP_BY_LOCATION"
                    )
                if conflict:
                    evidence = "; ".join(deterministic_location.negative_evidence)
                    raise ValueError(
                        "AI review conflicts with deterministic source evidence for "
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


def _company_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _upsert_company_watch(session: Session, posting: Posting, job: AIReviewJob) -> None:
    if not job.company_watch or not posting.company.strip():
        return
    key = _company_key(posting.company)
    watch = session.scalar(select(CompanyWatch).where(CompanyWatch.company_key == key))
    now = utc_now()
    if watch is None:
        session.add(
            CompanyWatch(
                id=str(uuid4()),
                company_name=posting.company.strip(),
                company_key=key,
                source_posting_id=posting.id,
                reason=job.company_watch_reason,
                role_patterns_json=json.dumps(
                    job.company_watch_role_patterns, ensure_ascii=False
                ),
                active=True,
                created_at=now,
                updated_at=now,
            )
        )
        return
    watch.company_name = posting.company.strip()
    watch.source_posting_id = posting.id
    watch.reason = job.company_watch_reason
    watch.role_patterns_json = json.dumps(
        job.company_watch_role_patterns, ensure_ascii=False
    )
    watch.active = True
    watch.updated_at = now


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
        if posting is None:
            raise ValueError(f"AI review references unknown posting: {job.posting_id}")
        _upsert_company_watch(session, posting, job)
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
            "hardline_status": job.hardline_status,
            "hardline_reasons_json": json.dumps(job.hardline_reasons, ensure_ascii=False),
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
            "pre_application_decision": job.pre_application_decision or "",
            "remote_scope": job.remote_scope,
            "work_authorization_status": job.work_authorization_status,
            "conditions_status": job.conditions_status,
            "official_source_status": job.official_source_status,
            "official_source_url": job.official_source_url,
            "official_source_location": job.official_source_location,
            "official_source_evidence_json": json.dumps(
                job.official_source_evidence, ensure_ascii=False
            ),
            "experience_evidence_json": json.dumps(
                [item.model_dump() for item in job.experience_evidence],
                ensure_ascii=False,
            ),
            "questions_for_user_json": json.dumps(job.questions_for_user, ensure_ascii=False),
            "company_watch": job.company_watch,
            "company_watch_reason": job.company_watch_reason,
            "company_watch_role_patterns_json": json.dumps(
                job.company_watch_role_patterns, ensure_ascii=False
            ),
            "recommended_cv_master_json": json.dumps(
                job.recommended_cv_master.model_dump()
                if job.recommended_cv_master is not None
                else {},
                ensure_ascii=False,
            ),
            "recommended_certifications_json": json.dumps(
                job.recommended_certifications, ensure_ascii=False
            ),
            "linkedin_skill_suggestions_json": json.dumps(
                job.linkedin_skill_suggestions, ensure_ascii=False
            ),
            "certification_inventory_complete": job.certification_inventory_complete,
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
