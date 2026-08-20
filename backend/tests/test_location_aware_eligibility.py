from jolt.evaluation_strategy import StrategyAssessment
from jolt.strategy_runtime import (
    _apply_location_eligibility,
    _normalized_location_scope,
)


def _assessment(
    *,
    eligibility: str = "eligible",
    recommendation: str = "strong_pursue",
    confidence: str = "high",
) -> StrategyAssessment:
    return StrategyAssessment(
        eligibility=eligibility,
        recommendation=recommendation,
        confidence=confidence,
        role_family_id="technical_support",
        fit_now=72,
        fit_by_interview=79,
        fit_on_the_job=84,
        interview_days=10,
        estimated_preparation_hours=8,
        dimensions={},
        strengths=(),
        gaps=(),
        blockers=(),
        uncertainties=(),
        preparation_plan=(),
    )


def test_location_scope_recognizes_spain_and_broad_regions() -> None:
    assert _normalized_location_scope("Madrid, Spain (Remote)") == "spain"
    assert _normalized_location_scope("A Coruña, Galicia, Spain") == "spain"
    assert _normalized_location_scope("European Union (Remote)") == "broad"
    assert _normalized_location_scope("EMEA (Remote)") == "broad"


def test_foreign_country_remote_role_is_ineligible_without_cross_border_evidence() -> None:
    result = _apply_location_eligibility(
        _assessment(),
        title="Technical Support Specialist",
        location="Portugal (Remote)",
        description="Remote technical support role.",
    )

    assert result.eligibility == "ineligible"
    assert result.recommendation == "do_not_pursue"
    assert result.confidence == "high"
    assert any(
        "does not establish that employment from Spain is permitted" in item
        for item in result.blockers
    )


def test_spain_remote_role_remains_actionable() -> None:
    original = _assessment()

    result = _apply_location_eligibility(
        original,
        title="Technical Support Engineer",
        location="Spain (Remote)",
        description="Remote role available across Spain.",
    )

    assert result == original


def test_eu_wide_remote_role_is_not_downgraded_by_location_alone() -> None:
    original = _assessment()

    result = _apply_location_eligibility(
        original,
        title="Technical Support Engineer",
        location="European Union (Remote)",
        description="Remote across the European Union.",
    )

    assert result == original


def test_explicit_foreign_residence_requirement_is_blocked() -> None:
    result = _apply_location_eligibility(
        _assessment(),
        title="Technical Support Specialist",
        location="Portugal (Remote)",
        description="Candidates must already be based in Portugal.",
    )

    assert result.eligibility == "ineligible"
    assert result.recommendation == "do_not_pursue"
    assert result.confidence == "high"
    assert any("residence or work authorization outside Spain" in item for item in result.blockers)


def test_existing_ineligible_assessment_is_preserved() -> None:
    original = _assessment(
        eligibility="ineligible",
        recommendation="do_not_pursue",
        confidence="high",
    )

    result = _apply_location_eligibility(
        original,
        title="Technical Support Specialist",
        location="Germany (Remote)",
        description="German role.",
    )

    assert result == original
