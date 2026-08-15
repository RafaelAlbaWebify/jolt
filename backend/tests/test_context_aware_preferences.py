from __future__ import annotations

from jolt.evaluation_strategy import (
    CapabilityEvidence,
    EligibilityRule,
    RoleFamily,
    StrategyProfile,
)
from jolt.job_search_preferences import JobSearchPreferences
from jolt.preference_aware_evaluation import preference_blockers, sanitize_capture_text
from jolt.strategy_runtime import calibrated_strategy_assessment


def _preferences() -> JobSearchPreferences:
    return JobSearchPreferences(
        languages=["Spanish", "English"],
        excluded_shifts=["night", "rotating", "weekend"],
        excluded_keywords=["dispatch", "field sales", "door to door", "commission only"],
    )


def _profile() -> StrategyProfile:
    return StrategyProfile(
        profile_id="context-test",
        version=1,
        role_families=[
            RoleFamily(
                id="support",
                label="Support",
                priority="primary",
                terms=["support engineer"],
                strategic_value=90,
            )
        ],
        capabilities=[
            CapabilityEvidence(
                id="support",
                label="Support",
                terms=["troubleshooting"],
                evidence_level=5,
            )
        ],
        eligibility_rules=[
            EligibilityRule(
                id="shift",
                label="Shift, weekend or on-call requirement",
                terms=["24/7", "night shift", "weekend coverage"],
                outcome="eligible_with_conditions",
            )
        ],
    )


def test_dispatch_company_marketing_does_not_block(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )
    text = (
        "End User Support Engineer. Advanced troubleshooting and escalation. "
        "Our software is helping to dispatch ambulances and keep trains moving."
    )

    assert preference_blockers(text) == []


def test_genuine_dispatch_requirement_still_blocks(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )

    assert preference_blockers("Can you support for dispatch activities?") == [
        "excluded keyword: dispatch"
    ]
    assert preference_blockers("Responsible for field dispatch operations.") == [
        "excluded keyword: dispatch"
    ]


def test_explicit_shift_requirements_still_block(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )

    assert preference_blockers("Technical Support Specialist - night shifts") == [
        "shift excluded by current preferences: night"
    ]
    assert preference_blockers("Premium Support Specialist, Weekend Coverage") == [
        "shift excluded by current preferences: weekend"
    ]


def test_linkedin_premium_24_7_support_is_removed() -> None:
    text = (
        "Technical Support Engineer. Troubleshooting incidents. "
        "Job search faster with Premium Premium subscribers are more likely to get hired. "
        "1-month free trial with 24/7 support. About the company Example Ltd."
    )

    sanitized = sanitize_capture_text(text)

    assert "24/7 support" not in sanitized
    assert "Technical Support Engineer" in sanitized
    assert "About the company Example Ltd." in sanitized


def test_platform_24_7_does_not_create_strategy_uncertainty(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )
    description = (
        "Advanced troubleshooting for enterprise users. "
        "Job search faster with Premium Premium subscribers are more likely to get hired. "
        "1-month free trial with 24/7 support. About the company Example Ltd."
    )

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Spain (Remote)",
        description=description,
    )

    assert assessment.eligibility == "eligible"
    assert assessment.uncertainties == ()


def test_real_24_7_requirement_remains_visible(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Spain (Remote)",
        description="Advanced troubleshooting in a mandatory 24/7 support rota.",
    )

    assert assessment.eligibility == "eligible_with_conditions"
    assert assessment.uncertainties == ("Shift, weekend or on-call requirement: 24/7.",)


def test_relocation_package_is_not_a_relocation_requirement(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )

    text = (
        "Home office friendly anywhere in Spain. Relocation package for international candidates."
    )

    assert preference_blockers(text) == []


def test_explicit_relocation_requirement_still_blocks(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )

    assert preference_blockers("This role requires relocation to Berlin.") == [
        "relocation is required"
    ]


def test_optional_languages_do_not_inherit_neighboring_mandatory_marker(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )

    text = "Fluent English is mandatory / Spanish or French or German are an advantage."

    assert preference_blockers(text) == []


def test_preferred_language_is_not_required(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )

    assert preference_blockers("Portuguese is preferred and training is provided.") == []


def test_explicit_foreign_language_requirement_still_blocks(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )

    assert preference_blockers("Fluent German is required for customer support.") == [
        "required language outside current preferences: german"
    ]


def test_weekend_benefit_wording_is_not_a_shift_requirement(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )

    text = "On Fridays we finish early so the fin de semana starts sooner."

    assert preference_blockers(text) == []


def test_temporary_employee_benefits_are_not_temporary_employment(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )

    text = "Benefits may vary for seasonal or temporary employees."

    assert preference_blockers(text) == []


def test_explicit_temporary_contract_still_blocks(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences", _preferences
    )

    assert preference_blockers("This is a temporary contract for six months.") == [
        "temporary or fixed-term employment"
    ]
