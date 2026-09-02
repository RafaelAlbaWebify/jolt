from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from jolt.ai_review_import import AIReviewImportRequest
from jolt.hardline_evidence import analyze_location_evidence

US_ONLY_CASES = [
    (
        "LucidLink Technical Support Engineer L2",
        "United States · Remote",
        "Applicants can be from anywhere in the US.",
    ),
    (
        "Unily Application Support Engineer",
        "United States · Remote",
        "This is a United States remote role.",
    ),
    (
        "Prompt Health Support Engineer",
        "United States · Remote",
        "Remote - USA. US employment and benefits apply.",
    ),
    (
        "Nebius Identity & Workplace Engineer",
        "United States · Remote",
        "United States remote. Requires 3+ years administering Microsoft Entra ID in production as a primary responsibility and substantial Google Workspace, Cloud Identity and GCP IAM experience.",
    ),
    (
        "Stripe Metronome Technical Support Engineer",
        "US Remote",
        "This requisition is remote within the United States.",
    ),
]


@pytest.mark.parametrize(("title", "location", "source_text"), US_ONLY_CASES)
def test_real_us_only_jobs_are_location_hardline_rejects(
    title: str,
    location: str,
    source_text: str,
) -> None:
    result = analyze_location_evidence(location=location, source_text=source_text)

    assert result.location_eligibility == "ineligible", title
    assert result.hardline_reject is True, title
    assert result.negative_evidence, title


def test_zone_and_co_country_of_residence_evidence_is_not_us_only() -> None:
    result = analyze_location_evidence(
        location="Remote",
        source_text=(
            "Systems & Support Engineer. Non-US team members may be engaged under contracts "
            "based on country of residence."
        ),
    )

    assert result.location_eligibility in {"eligible", "conditional"}
    assert result.hardline_reject is False
    assert any(
        "country of residence" in evidence.casefold() for evidence in result.positive_evidence
    )


def _base_job() -> dict[str, object]:
    return {
        "posting_id": "posting-1",
        "source_job_id": "job-1",
        "hardline_status": "PASS",
        "hardline_reasons": [],
        "location_eligibility": "eligible",
        "location_evidence": ["Spain / Europe remote hiring is explicitly supported."],
        "mandatory_requirements": [],
        "mandatory_requirement_results": [],
        "employment_constraints": [],
        "fit_analysis_allowed": True,
        "technical_fit_percent": 82,
        "final_decision": "pursue",
        "decision_reason": "Eligible and technically aligned.",
        "priority_score": 82,
        "geography_status": "eligible",
        "clearance_status": "clear",
        "language_status": "clear",
        "duplicate_of_posting_id": None,
        "summary": "Eligible support role.",
        "reasons": [],
    }


def _request(job: dict[str, object]) -> dict[str, object]:
    return {
        "contract_type": "jolt_ai_review",
        "contract_version": "1.1",
        "capture_run_id": "capture-1",
        "review_source": "chatgpt_source_first",
        "review_version": "hardline-test",
        "reviewed_at": datetime.now(UTC),
        "jobs": [job],
    }


def test_hardline_reject_cannot_be_overridden_by_high_fit() -> None:
    job = _base_job()
    job.update(
        {
            "hardline_status": "REJECT",
            "hardline_reasons": ["US-only remote requisition."],
            "location_eligibility": "ineligible",
            "fit_analysis_allowed": False,
            "technical_fit_percent": 95,
            "final_decision": "pursue",
            "decision_reason": "High technical similarity.",
            "geography_status": "ineligible",
        }
    )

    with pytest.raises(ValidationError):
        AIReviewImportRequest.model_validate(_request(job))


def test_hardline_reject_requires_reject_and_no_fit_score() -> None:
    job = _base_job()
    job.update(
        {
            "hardline_status": "REJECT",
            "hardline_reasons": ["US-only remote requisition."],
            "location_eligibility": "ineligible",
            "location_evidence": ["United States · Remote", "anywhere in the US"],
            "fit_analysis_allowed": False,
            "technical_fit_percent": None,
            "final_decision": "reject",
            "decision_reason": "US-only remote hardline.",
            "priority_score": 0,
            "geography_status": "ineligible",
        }
    )

    request = AIReviewImportRequest.model_validate(_request(job))
    reviewed = request.jobs[0]

    assert reviewed.final_decision == "reject"
    assert reviewed.technical_fit_percent is None
    assert reviewed.fit_analysis_allowed is False


def test_manual_review_cannot_sneak_into_fit_analysis() -> None:
    job = _base_job()
    job.update(
        {
            "hardline_status": "MANUAL_REVIEW",
            "hardline_reasons": ["Hiring geography is genuinely ambiguous."],
            "location_eligibility": "conditional",
            "fit_analysis_allowed": True,
            "technical_fit_percent": 80,
            "final_decision": "conditional",
        }
    )

    with pytest.raises(ValidationError):
        AIReviewImportRequest.model_validate(_request(job))


def test_nebius_unmet_material_mandatory_experience_is_hardline_reject() -> None:
    job = _base_job()
    requirement = {
        "requirement": "3+ years administering Microsoft Entra ID in production as a primary responsibility",
        "source_text": "Requires 3+ years administering Microsoft Entra ID in production as a primary responsibility.",
        "classification": "required",
        "candidate_evidence": "General Entra exposure and lab/study evidence only; no verified 3+ years primary production administration.",
        "result": "unmet",
        "hardline": True,
    }
    job.update(
        {
            "hardline_status": "REJECT",
            "hardline_reasons": [
                "US-only remote requisition.",
                "Material mandatory experience is unmet.",
            ],
            "location_eligibility": "ineligible",
            "location_evidence": ["United States · Remote"],
            "mandatory_requirements": [requirement],
            "mandatory_requirement_results": [requirement],
            "fit_analysis_allowed": False,
            "technical_fit_percent": None,
            "final_decision": "reject",
            "decision_reason": "US-only remote and material mandatory experience mismatch.",
            "priority_score": 0,
            "geography_status": "ineligible",
        }
    )

    request = AIReviewImportRequest.model_validate(_request(job))
    reviewed = request.jobs[0]

    assert reviewed.final_decision == "reject"
    assert reviewed.mandatory_requirement_results[0].result == "unmet"
    assert reviewed.mandatory_requirement_results[0].hardline is True
