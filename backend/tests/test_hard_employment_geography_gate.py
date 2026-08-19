from jolt.evaluation_strategy import StrategyAssessment
from jolt.strategy_runtime import _apply_location_eligibility


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
