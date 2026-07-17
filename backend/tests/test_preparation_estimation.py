from __future__ import annotations

from jolt.evaluation_strategy import StrategyProfile, assess_posting
from jolt.preparation_estimation import PreparationGap, estimate_preparation_hours


def test_duplicate_topics_are_counted_once_using_highest_gap() -> None:
    hours = estimate_preparation_hours(
        [
            PreparationGap("logs", "preparable_in_days", ("Log analysis",)),
            PreparationGap(
                "observability",
                "preparable_in_1_to_2_weeks",
                ("  log   analysis  ",),
            ),
        ]
    )

    assert hours == 10


def test_distinct_single_topic_capabilities_remain_distinct_workstreams() -> None:
    hours = estimate_preparation_hours(
        [
            PreparationGap("sql", "preparable_in_days", ("SQL troubleshooting",)),
            PreparationGap("api", "preparable_in_1_to_2_weeks", ("API diagnostics",)),
        ]
    )

    assert hours == 14


def test_capability_budget_is_divided_across_its_topics() -> None:
    hours = estimate_preparation_hours(
        [
            PreparationGap(
                "application-diagnostics",
                "preparable_in_1_to_2_weeks",
                ("Logs", "API diagnostics", "SQL troubleshooting"),
            )
        ]
    )

    assert hours == 12


def test_shared_topics_merge_after_budget_allocation() -> None:
    hours = estimate_preparation_hours(
        [
            PreparationGap(
                "application-diagnostics",
                "preparable_in_1_to_2_weeks",
                ("Logs", "SQL troubleshooting"),
            ),
            PreparationGap(
                "observability",
                "preparable_in_days",
                ("logs", "metrics"),
            ),
        ]
    )

    assert hours == 9


def test_capabilities_without_topics_keep_separate_fallbacks() -> None:
    hours = estimate_preparation_hours(
        [
            PreparationGap("capability-a", "preparable_in_days", ()),
            PreparationGap("capability-b", "preparable_in_days", ()),
        ]
    )

    assert hours == 8


def test_assess_posting_uses_deduplicated_preparation_topics() -> None:
    profile = StrategyProfile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "preparation-regression",
            "version": 1,
            "role_families": [
                {
                    "id": "application_support",
                    "label": "Application Support",
                    "priority": "primary",
                    "terms": ["application support"],
                    "strategic_value": 90,
                }
            ],
            "capabilities": [
                {
                    "id": "logs",
                    "label": "Logs",
                    "terms": ["logs"],
                    "evidence_level": 3,
                    "preparation_topics": ["Log analysis"],
                },
                {
                    "id": "observability",
                    "label": "Observability",
                    "terms": ["observability"],
                    "evidence_level": 2,
                    "preparation_topics": ["log analysis"],
                },
            ],
        }
    )

    result = assess_posting(
        profile,
        "Application Support Engineer",
        "Remote",
        "Investigate logs and observability data.",
    )

    assert result.estimated_preparation_hours == 10
