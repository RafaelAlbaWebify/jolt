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
        base_locality="Vigo, Galicia, Spain",
        max_hybrid_distance_km=30,
    )


def _install_preferences(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.preference_aware_evaluation.load_job_search_preferences",
        _preferences,
    )
    monkeypatch.setattr(
        "jolt.strategy_runtime.load_job_search_preferences",
        _preferences,
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


def test_default_hybrid_radius_is_30_km() -> None:
    assert JobSearchPreferences().max_hybrid_distance_km == 30


def test_infotree_hybrid_madrid_is_ineligible(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Madrid, Community of Madrid, Spain",
        description=(
            "Hybrid\n"
            "Contract\n"
            "Looking for a Customer/Technical Support Engineer for a long term "
            "contract position based in Madrid. Handle support cases, "
            "troubleshooting, root cause analysis and technical documentation."
        ),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"
    assert any(
        "outside the configured 30 km local radius" in blocker for blocker in assessment.blockers
    )


def test_remote_madrid_is_not_rejected_by_vigo_radius(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Madrid, Community of Madrid, Spain",
        description=(
            "Remote\n"
            "This role is fully remote from anywhere in Spain. "
            "Advanced troubleshooting for enterprise customers."
        ),
    )

    assert assessment.eligibility != "ineligible"
    assert not any("local radius" in blocker for blocker in assessment.blockers)


def test_hybrid_vigo_is_inside_local_area(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Vigo, Galicia, Spain",
        description="Hybrid\nAdvanced troubleshooting for enterprise customers.",
    )

    assert assessment.eligibility != "ineligible"
    assert not any("local radius" in blocker for blocker in assessment.blockers)


def test_hybrid_infrastructure_wording_is_not_work_mode(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Madrid, Community of Madrid, Spain",
        description=(
            "Support enterprise hybrid infrastructure, cloud services and "
            "network connectivity. The position does not state a workplace mode."
        ),
    )

    assert assessment.eligibility != "ineligible"
    assert not any("local radius" in blocker for blocker in assessment.blockers)


def test_unspecified_spanish_hybrid_location_requires_verification(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Spain",
        description="Hybrid\nAdvanced troubleshooting for enterprise customers.",
    )

    assert assessment.eligibility == "eligible_with_conditions"
    assert assessment.recommendation == "pursue_if_condition_met"
    assert any(
        "within the configured 30 km radius" in uncertainty
        for uncertainty in assessment.uncertainties
    )


def test_remote_anywhere_in_spain_is_not_foreign_residence_restriction(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("This role is fully remote from anywhere in Spain.") == []


def test_remote_from_spain_is_not_foreign_residence_restriction(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("Candidates may work remotely from Spain.") == []


def test_madrid_based_remote_role_is_not_foreign_country_restriction(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("Remote role for candidates based in Madrid, Spain.") == []


def test_explicit_remote_germany_residence_requirement_still_blocks(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("This position is remote only within Germany.") == [
        "remote work is restricted to residence in another country"
    ]


def test_explicit_germany_based_candidate_requirement_still_blocks(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("Only for candidates already based in Germany.") == [
        "remote work is restricted to residence in another country"
    ]


def test_portuguese_preferred_after_required_english_is_not_required(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    text = "Fluent Spanish and professional-level English are required; Portuguese is preferred."

    assert preference_blockers(text) == []


def test_short_portugues_alias_does_not_match_inside_portuguese(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    text = "Professional-level English is required. Portuguese is preferred."

    assert preference_blockers(text) == []


def test_amazon_benefits_status_example_is_not_temporary_job(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    text = (
        "Benefits can vary by location, regularly scheduled hours, "
        "length of employment, and job status such as seasonal or "
        "temporary employment."
    )

    assert preference_blockers(text) == []


def test_explicit_temporary_employment_duration_still_blocks(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("This is temporary employment for six months.") == [
        "temporary or fixed-term employment"
    ]


def test_legacy_20km_uncertainty_is_removed_from_remote_role(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    profile = _profile()
    profile.eligibility_rules.append(
        EligibilityRule(
            id="legacy-work-mode",
            label=(
                "Onsite or hybrid work requires confirmation that the "
                "workplace is within 20 km of Vigo city"
            ),
            terms=["hybrid"],
            outcome="uncertain",
        )
    )

    assessment = calibrated_strategy_assessment(
        profile,
        title="Technical Support Specialist",
        location="Spain",
        description=(
            "This role is fully remote from anywhere in Spain. "
            "Support hybrid infrastructure for customers."
        ),
    )

    assert assessment.eligibility == "eligible"
    assert not any("20 km" in uncertainty for uncertainty in assessment.uncertainties)


def test_legacy_uncertainty_is_replaced_by_30km_runtime_rule(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    profile = _profile()
    profile.eligibility_rules.append(
        EligibilityRule(
            id="legacy-work-mode",
            label=(
                "Onsite or hybrid work requires confirmation that the "
                "workplace is within 20 km of Vigo city"
            ),
            terms=["hybrid"],
            outcome="uncertain",
        )
    )

    assessment = calibrated_strategy_assessment(
        profile,
        title="Technical Support Engineer",
        location="Spain",
        description="Hybrid\nAdvanced troubleshooting.",
    )

    assert assessment.eligibility == "eligible_with_conditions"
    assert any("configured 30 km radius" in uncertainty for uncertainty in assessment.uncertainties)
    assert not any("20 km" in uncertainty for uncertainty in assessment.uncertainties)


def test_legacy_uncertainty_does_not_prevent_madrid_rejection(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    profile = _profile()
    profile.eligibility_rules.append(
        EligibilityRule(
            id="legacy-work-mode",
            label=(
                "Onsite or hybrid work requires confirmation that the "
                "workplace is within 20 km of Vigo city"
            ),
            terms=["hybrid"],
            outcome="uncertain",
        )
    )

    assessment = calibrated_strategy_assessment(
        profile,
        title="Technical Support Engineer",
        location="Madrid, Community of Madrid, Spain",
        description="Hybrid\nAdvanced troubleshooting.",
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"
    assert any(
        "outside the configured 30 km local radius" in blocker for blocker in assessment.blockers
    )


def test_structured_madrid_hybrid_location_is_ineligible(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Madrid, Community of Madrid, Spain (Hybrid)",
        description="Advanced troubleshooting for enterprise customers.",
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"
    assert any(
        "outside the configured 30 km local radius" in blocker for blocker in assessment.blockers
    )


def test_structured_barcelona_onsite_location_is_ineligible(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Barcelona, Spain · On-site",
        description="Advanced troubleshooting for enterprise customers.",
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"


def test_structured_vigo_hybrid_location_remains_actionable(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Vigo, Galicia, Spain (Hybrid)",
        description="Advanced troubleshooting for enterprise customers.",
    )

    assert assessment.eligibility != "ineligible"
    assert not any("local radius" in blocker for blocker in assessment.blockers)


def test_structured_remote_location_does_not_trigger_radius_block(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Madrid, Community of Madrid, Spain (Remote)",
        description="Advanced troubleshooting for enterprise customers.",
    )

    assert assessment.eligibility != "ineligible"
    assert not any("local radius" in blocker for blocker in assessment.blockers)


def test_location_remote_and_description_hybrid_is_conflicting_evidence(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Spain (Remote)",
        description=(
            "This is a hybrid role with advanced troubleshooting for enterprise customers."
        ),
    )

    assert assessment.eligibility == "eligible_with_conditions"
    assert assessment.recommendation == "pursue_if_condition_met"
    assert any(
        "conflicting explicit remote and hybrid/onsite evidence" in uncertainty
        for uncertainty in assessment.uncertainties
    )


def test_hybrid_infrastructure_still_does_not_become_work_mode(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Madrid, Community of Madrid, Spain",
        description=(
            "Support enterprise hybrid infrastructure and cloud services. "
            "No workplace mode is stated."
        ),
    )

    assert assessment.eligibility != "ineligible"
    assert not any("local radius" in blocker for blocker in assessment.blockers)
