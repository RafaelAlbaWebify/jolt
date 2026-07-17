from __future__ import annotations

from jolt.evaluation_strategy import StrategyProfile, _matched_terms, assess_posting


def _profile() -> StrategyProfile:
    return StrategyProfile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "role-family-regression",
            "version": 1,
            "role_families": [
                {
                    "id": "application_support",
                    "label": "Application Support",
                    "priority": "primary",
                    "terms": ["application support", "support engineer"],
                    "strategic_value": 90,
                },
                {
                    "id": "network_support",
                    "label": "Network Support",
                    "priority": "secondary",
                    "terms": ["network support", "network support engineer"],
                    "strategic_value": 80,
                },
                {
                    "id": "architecture_dba",
                    "label": "Architecture and DBA",
                    "priority": "excluded",
                    "terms": ["solution architect", "database architect", "architecture"],
                    "strategic_value": 10,
                },
                {
                    "id": "software_development",
                    "label": "Software Development",
                    "priority": "excluded",
                    "terms": ["backend developer", "software developer"],
                    "strategic_value": 5,
                },
            ],
            "capabilities": [
                {
                    "id": "incident_support",
                    "label": "Incident support",
                    "terms": ["incident", "troubleshooting"],
                    "evidence_level": 4,
                }
            ],
            "preparation": {
                "hours_per_week": 20,
                "default_days_until_technical": 10,
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
    )


def test_network_support_title_beats_incidental_architecture_description() -> None:
    result = assess_posting(
        _profile(),
        "VyOS Network Support Engineer",
        "Remote Europe",
        (
            "Troubleshoot incidents and customer network issues. Work with the product "
            "architecture team when escalation is required."
        ),
    )

    assert result.role_family_id == "network_support"
    assert not any("Excluded role family" in blocker for blocker in result.blockers)


def test_excluded_developer_title_beats_support_language_in_description() -> None:
    result = assess_posting(
        _profile(),
        "Backend Developer",
        "Remote",
        "Support production incidents and troubleshoot customer integrations.",
    )

    assert result.role_family_id == "software_development"
    assert result.recommendation == "do_not_pursue"
    assert any("Excluded role family" in blocker for blocker in result.blockers)


def test_more_specific_title_phrase_wins_deterministically() -> None:
    result = assess_posting(
        _profile(),
        "Network Support Engineer",
        "Remote",
        "Application support may be required during incident escalation.",
    )

    assert result.role_family_id == "network_support"


def test_term_matching_uses_word_boundaries() -> None:
    assert _matched_terms("support engineer", ["support"]) == ("support",)
    assert _matched_terms("supporting engineering teams", ["support"]) == ()
    assert _matched_terms("architecting resilient systems", ["architect"]) == ()
    assert _matched_terms("database architect", ["architect"]) == ("architect",)
