from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from jolt.evaluation_strategy import StrategyProfile, assess_posting, load_strategy_profile


def _profile(**overrides: object) -> StrategyProfile:
    payload: dict[str, object] = {
        "schema_version": 1,
        "profile_id": "synthetic-support-profile",
        "version": 1,
        "display_name": "Synthetic Support Candidate",
        "role_families": [
            {
                "id": "application_support",
                "label": "Application Support",
                "priority": "primary",
                "terms": ["application support", "technical support engineer"],
                "strategic_value": 90,
            },
            {
                "id": "software_development",
                "label": "Software Development",
                "priority": "excluded",
                "terms": ["software developer", "backend developer"],
                "strategic_value": 10,
            },
        ],
        "capabilities": [
            {
                "id": "incident_management",
                "label": "Incident management",
                "terms": ["incident", "root cause", "escalation"],
                "evidence_level": 5,
                "transferable_to": ["production support"],
                "preparation_topics": [],
            },
            {
                "id": "sql_support",
                "label": "SQL support",
                "terms": ["sql", "database troubleshooting"],
                "evidence_level": 2,
                "transferable_to": ["data investigation"],
                "preparation_topics": [
                    "Practise read-only SQL diagnosis and explain escalation boundaries."
                ],
            },
            {
                "id": "api_support",
                "label": "API troubleshooting",
                "terms": ["api", "rest integration"],
                "evidence_level": 3,
                "transferable_to": ["integration support"],
                "preparation_topics": [
                    "Practise HTTP status, authentication, payload and correlation-ID scenarios."
                ],
            },
        ],
        "eligibility_rules": [
            {
                "id": "unsupported_residency",
                "label": "Unsupported residency requirement",
                "terms": ["must reside in the united states"],
                "outcome": "ineligible",
            },
            {
                "id": "on_call",
                "label": "On-call expectation",
                "terms": ["on-call"],
                "outcome": "eligible_with_conditions",
            },
        ],
        "preparation": {
            "hours_per_week": 20,
            "default_days_until_technical": 10,
            "ai_guided_study": True,
            "documentation": True,
            "labs": True,
            "mock_interviews": True,
            "maximum_parallel_processes": 3,
        },
        "weights": {
            "role_alignment": 20,
            "demonstrated_capability": 25,
            "transferable_capability": 10,
            "gap_feasibility": 15,
            "opportunity_quality": 15,
            "strategic_value": 15,
        },
    }
    payload.update(overrides)
    return StrategyProfile.model_validate(payload)


def test_profile_weights_must_total_one_hundred() -> None:
    with pytest.raises(ValidationError, match="must total 100"):
        _profile(
            weights={
                "role_alignment": 20,
                "demonstrated_capability": 20,
                "transferable_capability": 10,
                "gap_feasibility": 10,
                "opportunity_quality": 10,
                "strategic_value": 10,
            }
        )


def test_profile_loads_from_private_json_path(tmp_path: Path) -> None:
    profile = _profile()
    path = tmp_path / "candidate.private.json"
    path.write_text(json.dumps(profile.model_dump()), encoding="utf-8")

    loaded = load_strategy_profile(path)

    assert loaded.version_id == "synthetic-support-profile:v1"
    assert loaded.display_name == "Synthetic Support Candidate"


def test_interview_window_can_turn_trainable_gaps_into_pursue() -> None:
    result = assess_posting(
        _profile(),
        "Application Support Engineer",
        "Remote",
        (
            "Own incidents and escalation for a SaaS product. Troubleshoot SQL, API and REST "
            "integration failures with engineering."
        ),
        days_until_technical=10,
    )

    assert result.eligibility == "eligible"
    assert result.role_family_id == "application_support"
    assert result.fit_by_interview > result.fit_now
    assert result.fit_on_the_job >= result.fit_by_interview
    assert result.recommendation in {"strong_pursue", "pursue"}
    assert result.estimated_preparation_hours == 14
    assert {gap.gap_type for gap in result.gaps} == {
        "preparable_in_days",
        "preparable_in_1_to_2_weeks",
    }
    assert len(result.preparation_plan) == 2


def test_short_window_does_not_pretend_experience_gap_is_closed() -> None:
    profile = _profile(
        capabilities=[
            {
                "id": "professional_backend_development",
                "label": "Professional backend development",
                "terms": ["design and build backend services"],
                "evidence_level": 0,
                "preparation_topics": ["Gain professional production experience."],
            }
        ]
    )

    result = assess_posting(
        profile,
        "Application Support Engineer",
        "Remote",
        "Application support plus design and build backend services.",
        days_until_technical=14,
    )

    assert result.fit_by_interview == result.fit_now
    assert result.gaps[0].gap_type == "experience_gap"
    assert result.estimated_preparation_hours == 120
    assert result.preparation_plan == ()


def test_ineligible_rule_overrides_high_technical_fit() -> None:
    result = assess_posting(
        _profile(),
        "Application Support Engineer",
        "United States",
        (
            "Must reside in the United States. Own incident, SQL and API troubleshooting for "
            "production support."
        ),
    )

    assert result.eligibility == "ineligible"
    assert result.recommendation == "do_not_pursue"
    assert result.blockers


def test_excluded_role_family_is_not_rescued_by_keywords() -> None:
    result = assess_posting(
        _profile(),
        "Backend Developer",
        "Remote",
        "Backend developer responsible for API services and incident response.",
    )

    assert result.role_family_id == "software_development"
    assert result.recommendation == "do_not_pursue"
    assert "Excluded role family" in result.blockers[0]


def test_unknown_posting_reduces_confidence() -> None:
    result = assess_posting(_profile(), "Technical Specialist", "", "General duties.")

    assert result.confidence == "low"
    assert result.role_family_id is None
