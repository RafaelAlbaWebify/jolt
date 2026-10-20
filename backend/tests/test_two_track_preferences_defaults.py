from jolt.job_search_preferences import JobSearchPreferences


def test_two_track_discovery_fallback_salary_and_shifts():
    preferences = JobSearchPreferences()
    assert preferences.expected_salary_eur_min == 17094
    assert preferences.excluded_shifts == []
    assert preferences.max_hybrid_distance_km == 30


def test_existing_shift_preferences_are_respected():
    preferences = JobSearchPreferences.model_validate({
        "excluded_shifts": ["night", "weekend"],
        "expected_salary_eur_min": 17094,
    })
    assert preferences.excluded_shifts == ["night", "weekend"]
