from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from jolt.ai_review_import import AIReviewImportRequest
from jolt.linkedin_batch_review import BatchAIReviewImportRequest


def _job(**overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "posting_id": "posting-encamina",
        "source_job_id": "4469775080",
        "hardline_status": "PASS",
        "hardline_reasons": [],
        "location_eligibility": "conditional",
        "location_evidence": [
            "LinkedIn: Sagunto/Sagunt, Remote",
            "Official Factorial ATS: Híbrido (Sagunto, VC, España)",
        ],
        "mandatory_requirements": [],
        "mandatory_requirement_results": [],
        "employment_constraints": ["Official work model conflicts with LinkedIn Remote"],
        "fit_analysis_allowed": True,
        "technical_fit_percent": 90,
        "final_decision": "conditional",
        "decision_reason": "High technical fit; hold until location/work model is verified.",
        "decision": "conditional",
        "priority_score": 82,
        "geography_status": "conditional",
        "clearance_status": "clear",
        "language_status": "clear",
        "technical_fit": 90,
        "source_conflict": True,
        "linkedin_work_model": "remote",
        "official_work_model": "hybrid",
        "authoritative_source": "official_ats",
        "official_source_url": (
            "https://encamina.factorialhr.com/job_posting/application-support-technician-324733"
        ),
        "remote_status": "not_confirmed_remote",
        "location_verification_status": "conflict",
        "source_confidence": "high",
        "duplicate_of_posting_id": None,
        "summary": "High technical fit with unresolved work-model conflict.",
        "reasons": ["Official ATS is authoritative for the published work model."],
    }
    payload.update(overrides)
    return payload


def _request(job: dict[str, object]) -> dict[str, object]:
    return {
        "contract_type": "jolt_ai_review",
        "contract_version": "1.2",
        "capture_run_id": "capture-1",
        "review_source": "chatgpt_source_first",
        "review_version": "source-verification-test",
        "reviewed_at": datetime.now(UTC),
        "jobs": [job],
    }


def test_encamina_style_conflict_keeps_high_fit_but_caps_decision() -> None:
    request = AIReviewImportRequest.model_validate(_request(_job()))
    reviewed = request.jobs[0]

    assert reviewed.technical_fit_percent == 90
    assert reviewed.source_conflict is True
    assert reviewed.remote_status == "not_confirmed_remote"
    assert reviewed.location_verification_status == "conflict"
    assert reviewed.geography_status == "conditional"
    assert reviewed.final_decision == "conditional"


def test_linkedin_remote_cannot_be_positive_without_official_confirmation() -> None:
    job = _job(
        source_conflict=False,
        official_work_model="unknown",
        authoritative_source="linkedin",
        official_source_url="",
        remote_status="not_confirmed_remote",
        location_verification_status="not_found",
        source_confidence="low",
        location_eligibility="eligible",
        geography_status="eligible",
        final_decision="pursue",
        decision="pursue",
    )

    with pytest.raises(ValidationError, match="remote_status=confirmed_remote"):
        AIReviewImportRequest.model_validate(_request(job))


def test_linkedin_remote_positive_requires_official_remote_authority() -> None:
    job = _job(
        source_conflict=False,
        official_work_model="remote",
        authoritative_source="official_ats",
        remote_status="confirmed_remote",
        location_verification_status="verified",
        source_confidence="high",
        location_eligibility="eligible",
        geography_status="eligible",
        final_decision="pursue",
        decision="pursue",
    )

    request = AIReviewImportRequest.model_validate(_request(job))
    assert request.jobs[0].final_decision == "pursue"


def test_divergent_known_work_models_must_set_conflict() -> None:
    job = _job(source_conflict=False)

    with pytest.raises(ValidationError, match="source_conflict must be true"):
        AIReviewImportRequest.model_validate(_request(job))


def test_contract_12_requires_source_verification_fields() -> None:
    job = _job()
    del job["official_source_url"]

    with pytest.raises(ValidationError, match="missing source-verification fields"):
        AIReviewImportRequest.model_validate(_request(job))


def test_batch_contract_12_enforces_same_source_rule() -> None:
    payload = {
        "contract_type": "jolt_ai_review_batch",
        "contract_version": "1.0",
        "ai_review_contract_version": "1.2",
        "discovery_batch_id": "batch-1",
        "review_source": "chatgpt_source_first",
        "review_version": "source-verification-test",
        "reviewed_at": datetime.now(UTC),
        "jobs": [
            _job(
                source_conflict=False,
                official_work_model="unknown",
                authoritative_source="linkedin",
                official_source_url="",
                remote_status="not_confirmed_remote",
                location_verification_status="not_found",
                source_confidence="low",
                location_eligibility="eligible",
                geography_status="eligible",
                final_decision="pursue",
                decision="pursue",
            )
        ],
    }

    with pytest.raises(ValidationError, match="remote_status=confirmed_remote"):
        BatchAIReviewImportRequest.model_validate(payload)
