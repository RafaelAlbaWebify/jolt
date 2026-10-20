from jolt.job_search_preferences import JobSearchPreferences
from jolt.preference_aware_evaluation import preference_blockers


def test_temporary_and_fixed_term_not_hard_rejected(monkeypatch):
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences",
        lambda: JobSearchPreferences(excluded_shifts=[], excluded_keywords=[]),
    )
    for description in [
        "Temporary role: office-based administrative assistant in Vigo.",
        "Fixed-term customer support contract in Spain.",
        "Paid internship in technical support.",
    ]:
        assert preference_blockers(description) == []


def test_explicit_saved_shift_exclusion_still_enforced(monkeypatch):
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences",
        lambda: JobSearchPreferences(excluded_shifts=["night"], excluded_keywords=[]),
    )
    assert "shift excluded by current preferences: night" in preference_blockers(
        "Night shifts required."
    )
