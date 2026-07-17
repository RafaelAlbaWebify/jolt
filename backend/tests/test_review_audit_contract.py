from __future__ import annotations

from jolt.review_audit import _is_versioned_private_profile, _validate_evaluation_contract


def _private_item() -> dict[str, object]:
    return {
        "profile_version_id": "private-profile:v2",
        "engine_version": "profile-rules-v4",
        "ranking_score": 72,
        "eligibility": "eligible_with_conditions",
        "role_family_id": "application_support",
        "fit_now": 61,
        "fit_by_interview": 72,
        "fit_on_the_job": 80,
        "interview_days": 10,
        "estimated_preparation_hours": 14,
        "strategy_gaps": [],
        "preparation_plan": [],
    }


def test_private_strategy_v4_contract_is_valid() -> None:
    assert _validate_evaluation_contract(_private_item(), "Example") == []


def test_private_strategy_v3_history_contract_remains_valid() -> None:
    item = _private_item()
    item["engine_version"] = "profile-rules-v3"
    assert _validate_evaluation_contract(item, "Historical") == []


def test_legacy_contract_remains_valid() -> None:
    item = {
        "profile_version_id": "rafael-job-search:v2",
        "engine_version": "profile-rules-v2",
    }
    assert _validate_evaluation_contract(item, "Legacy") == []


def test_private_strategy_requires_versioned_profile_identity() -> None:
    item = _private_item()
    item["profile_version_id"] = "private-profile"
    findings = _validate_evaluation_contract(item, "Example")
    assert any("private profile version is invalid" in finding["message"] for finding in findings)


def test_private_strategy_requires_consistent_fit_progression() -> None:
    item = _private_item()
    item["fit_by_interview"] = 55
    findings = _validate_evaluation_contract(item, "Example")
    messages = [finding["message"] for finding in findings]
    assert any("fit progression is inconsistent" in message for message in messages)
    assert any("ranking score does not match" in message for message in messages)


def test_private_profile_identity_validation() -> None:
    assert _is_versioned_private_profile("candidate-profile:v12")
    assert not _is_versioned_private_profile("candidate-profile")
    assert not _is_versioned_private_profile("Candidate Profile:v2")
