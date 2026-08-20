import pytest

from jolt.evaluation_strategy import StrategyAssessment
from jolt.strategy_runtime import (
    _apply_location_eligibility,
    _normalized_location_scope,
)


def _assessment() -> StrategyAssessment:
    return StrategyAssessment(
        eligibility="eligible",
        recommendation="strong_pursue",
        confidence="high",
        role_family_id="technical_support",
        fit_now=90,
        fit_by_interview=100,
        fit_on_the_job=100,
        interview_days=10,
        estimated_preparation_hours=10,
        dimensions={},
        strengths=(),
        gaps=(),
        blockers=(),
        uncertainties=(),
        preparation_plan=(),
    )


def test_real_ibase_t_us_remote_case_is_ineligible() -> None:
    result = _apply_location_eligibility(
        _assessment(),
        title="Technical Support Engineer II",
        location="United States",
        description=(
            "Remote. "
            "At this time, iBase-t does not sponsor visas for employment. "
            "Applicants must have valid work authorization to be considered."
        ),
    )
    assert result.eligibility == "ineligible"
    assert result.recommendation == "do_not_pursue"


def test_foreign_remote_country_is_ineligible() -> None:
    result = _apply_location_eligibility(
        _assessment(),
        title="Application Support Engineer",
        location="United Kingdom (Remote)",
        description="Fully remote technical support position.",
    )
    assert result.eligibility == "ineligible"
    assert result.recommendation == "do_not_pursue"


def test_us_state_remote_is_ineligible() -> None:
    result = _apply_location_eligibility(
        _assessment(),
        title="Support Engineer",
        location="Austin, TX (Remote)",
        description="Remote support role.",
    )
    assert result.eligibility == "ineligible"


def test_spain_remote_remains_eligible() -> None:
    original = _assessment()
    assert (
        _apply_location_eligibility(
            original,
            title="Technical Support Engineer",
            location="Spain (Remote)",
            description="Remote role available across Spain.",
        )
        == original
    )


def test_europe_and_emea_remain_allowed() -> None:
    for location in ("Europe (Remote)", "EMEA"):
        original = _assessment()
        assert (
            _apply_location_eligibility(
                original,
                title="Technical Support Engineer",
                location=location,
                description="Remote role available across Europe and EMEA.",
            )
            == original
        )


def test_plain_remote_requires_confirmation() -> None:
    result = _apply_location_eligibility(
        _assessment(),
        title="Technical Support Engineer",
        location="Remote",
        description="This role is remote.",
    )
    assert result.eligibility == "eligible_with_conditions"
    assert result.recommendation == "pursue_if_condition_met"
    assert result.confidence == "low"


def test_explicit_spain_permission_overrides_foreign_location() -> None:
    original = _assessment()
    assert (
        _apply_location_eligibility(
            original,
            title="Technical Support Engineer",
            location="United States",
            description="Candidates based in Spain are eligible to work remotely.",
        )
        == original
    )


def test_explicit_global_b2b_overrides_foreign_location() -> None:
    original = _assessment()
    assert (
        _apply_location_eligibility(
            original,
            title="Automation Engineer",
            location="United States",
            description="Remote worldwide. International B2B contracting is supported.",
        )
        == original
    )


@pytest.mark.parametrize(
    "location",
    (
        "Canada (Remote)",
        "Australia (Remote)",
        "India (Remote)",
        "Singapore (Remote)",
        "Japan (Remote)",
        "Mexico (Remote)",
        "Brazil (Remote)",
        "South Africa (Remote)",
        "United Arab Emirates (Remote)",
        "New Zealand (Remote)",
        "Argentina (Remote)",
        "South Korea (Remote)",
    ),
)
def test_global_country_matrix_is_hard_blocked_without_spain_evidence(
    location: str,
) -> None:
    result = _apply_location_eligibility(
        _assessment(),
        title="Technical Support Engineer",
        location=location,
        description="Fully remote technical support position.",
    )

    assert result.eligibility == "ineligible"
    assert result.recommendation == "do_not_pursue"
    assert result.confidence == "high"


@pytest.mark.parametrize(
    "location",
    (
        "Spain / Portugal (Remote)",
        "United States / Canada / EMEA",
        "Europe (Remote)",
        "European Union (Remote)",
        "Worldwide Remote",
        "Global Remote",
    ),
)
def test_explicit_spain_compatible_scope_wins_in_mixed_geography(
    location: str,
) -> None:
    original = _assessment()

    result = _apply_location_eligibility(
        original,
        title="Technical Support Engineer",
        location=location,
        description="Remote technical support role.",
    )

    assert result == original


def test_country_matching_uses_boundaries_not_substrings() -> None:
    assert _normalized_location_scope("India (Remote)") == "foreign_country"
    assert _normalized_location_scope("Indianapolis") == "unknown"
    assert _normalized_location_scope("China (Remote)") == "foreign_country"
    assert _normalized_location_scope("Chinatown") == "unknown"


def test_foreign_country_becomes_allowed_with_explicit_spain_permission() -> None:
    original = _assessment()

    result = _apply_location_eligibility(
        original,
        title="Application Support Engineer",
        location="Canada (Remote)",
        description="Candidates based in Spain may work remotely in this position.",
    )

    assert result == original


def test_bare_remote_stays_confirmation_not_automatic_permission() -> None:
    result = _apply_location_eligibility(
        _assessment(),
        title="Application Support Engineer",
        location="Remote",
        description="Fully remote position.",
    )

    assert result.eligibility == "eligible_with_conditions"
    assert result.recommendation == "pursue_if_condition_met"
    assert result.confidence == "low"


def test_negative_spain_statement_never_grants_cross_border_permission() -> None:
    result = _apply_location_eligibility(
        _assessment(),
        title="Technical Support Engineer",
        location="Canada (Remote)",
        description="Candidates based in Spain are not eligible for this position.",
    )

    assert result.eligibility == "ineligible"
    assert result.recommendation == "do_not_pursue"


def test_negative_spain_work_statement_never_grants_permission() -> None:
    result = _apply_location_eligibility(
        _assessment(),
        title="Technical Support Engineer",
        location="United States (Remote)",
        description="Employees may not work remotely from Spain.",
    )

    assert result.eligibility == "ineligible"
    assert result.recommendation == "do_not_pursue"


def test_positive_spain_permission_requires_actual_permission_language() -> None:
    original = _assessment()

    result = _apply_location_eligibility(
        original,
        title="Technical Support Engineer",
        location="Canada (Remote)",
        description="Candidates based in Spain are eligible for this position.",
    )

    assert result == original


def test_international_falls_is_not_global_scope() -> None:
    assert _normalized_location_scope("International Falls, MN") == "foreign_country"


def test_generic_international_location_is_not_automatic_permission() -> None:
    assert _normalized_location_scope("International") == "unknown"
