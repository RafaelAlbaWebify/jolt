from __future__ import annotations

from jolt.calibration_semantics import semantic_findings


def test_flags_likely_target_without_role_family() -> None:
    findings = semantic_findings(
        {
            "posting_id": "one",
            "title": "Technical Support L2",
            "role_family_id": None,
            "recommendation": "defer",
            "estimated_preparation_hours": 10,
        }
    )

    assert any(item["code"] == "likely_target_missing_role_family" for item in findings)


def test_flags_rejected_support_or_network_title() -> None:
    findings = semantic_findings(
        {
            "posting_id": "two",
            "title": "Senior Network Engineer",
            "role_family_id": "unrelated_business_functions",
            "recommendation": "do_not_pursue",
            "estimated_preparation_hours": 20,
        }
    )

    assert any(item["code"] == "support_title_rejected" for item in findings)


def test_flags_high_preparation_hours() -> None:
    findings = semantic_findings(
        {
            "posting_id": "three",
            "title": "Active Directory Engineer",
            "role_family_id": "m365_identity",
            "recommendation": "pursue_if_condition_met",
            "estimated_preparation_hours": 49,
        }
    )

    assert any(item["code"] == "preparation_hours_high" for item in findings)


def test_clean_target_produces_no_findings() -> None:
    findings = semantic_findings(
        {
            "posting_id": "four",
            "title": "Network Support Engineer",
            "role_family_id": "network_support",
            "recommendation": "pursue",
            "estimated_preparation_hours": 20,
        }
    )

    assert findings == []
