from __future__ import annotations

from jolt.evaluation_strategy import StrategyProfile, assess_posting
from jolt.preparation_estimation import PreparationGap, estimate_preparation_hours


def test_duplicate_topics_are_counted_once_using_highest_gap() -> None:
    hours = estimate_preparation_hours(
        [
            PreparationGap(
                capability_id="logs",
                gap_type="preparable_in_days",
                preparation_topics=("Log analysis",),
            ),
            PreparationGap(
                capability_id="observability",
                gap_type="preparable_in_1_to_2_weeks",
                preparation_topics=("  log   analysis  ",),
            ),
        ]
    )

    assert hours == 10


def test_distinct_topics_remain_distinct_workstreams() -> None:
    hours = estimate_preparation_hours(
        [
            PreparationGap(
                capability_id="sql",
                gap_type="preparable_in_days",
                preparation_topics=("SQL troubleshooting",),
            ),
            PreparationGap(
                capability_id="api",
                gap_type="preparable_in_1_to_2_weeks",
                preparation_topics=("API diagnostics",),
            ),
        ]
    )

    assert hours == 14


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
