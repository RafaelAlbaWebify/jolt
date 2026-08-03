from __future__ import annotations

from jolt import review_audit
from jolt.review_audit import (
    _is_versioned_private_profile,
    _load_current_opportunities,
    _validate_evaluation_contract,
)


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


def test_current_opportunity_loader_uses_compact_index_and_bounded_details(
    monkeypatch,
) -> None:
    index = [
        {
            "posting_id": f"posting-{position}",
            "title": f"Opportunity {position}",
        }
        for position in range(40)
    ]
    calls: list[str] = []

    def fake_get_json(url: str) -> object:
        calls.append(url)
        if url.endswith("/api/opportunity-index"):
            return index
        posting_id = url.rsplit("/", 1)[-1]
        return {
            "posting_id": posting_id,
            "title": f"Detail {posting_id}",
        }

    monkeypatch.setattr(review_audit, "_get_json", fake_get_json)

    loaded_index, details, findings = _load_current_opportunities()

    assert loaded_index == index
    assert len(details) == 40
    assert findings == []
    assert calls[0].endswith("/api/opportunity-index")
    assert all("/api/opportunity-detail/" in url for url in calls[1:])
    assert not any(url.endswith("/api/opportunities") for url in calls)


def test_current_opportunity_loader_reports_bad_rows_without_unbounded_fallback(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def fake_get_json(url: str) -> object:
        calls.append(url)
        if url.endswith("/api/opportunity-index"):
            return [
                "not-an-object",
                {"title": "Missing identity"},
                {"posting_id": "posting-1", "title": "Valid"},
            ]
        return {"posting_id": "posting-1", "title": "Valid"}

    monkeypatch.setattr(review_audit, "_get_json", fake_get_json)

    index, details, findings = _load_current_opportunities()

    assert len(index) == 2
    assert details == [{"posting_id": "posting-1", "title": "Valid"}]
    assert len(findings) == 2
    assert any("non-object row" in finding["message"] for finding in findings)
    assert any("missing posting_id" in finding["message"] for finding in findings)
    assert not any(url.endswith("/api/opportunities") for url in calls)
