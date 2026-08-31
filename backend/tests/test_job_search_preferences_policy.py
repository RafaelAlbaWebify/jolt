from __future__ import annotations

from jolt.job_search_preferences import ALL_SHIFTS, JobSearchPreferences


def test_employment_urgency_normalizes_legacy_shift_exclusions() -> None:
    preferences = JobSearchPreferences.model_validate(
        {
            "preferred_shifts": ["business_hours", "flexible"],
            "excluded_shifts": ["night", "rotating", "weekend"],
            "employment_urgency": "normal",
            "direct_contact_before_apply": True,
        }
    )

    assert preferences.employment_urgency == "high"
    assert preferences.preferred_shifts == ALL_SHIFTS
    assert preferences.excluded_shifts == []
    assert preferences.geography_policy == "explicit_restrictions_only"
    assert preferences.direct_contact_before_apply is False
