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


def test_explicit_spain_remote_removes_obsolete_contracting_uncertainty(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    profile = _profile()
    profile.eligibility_rules.append(
        EligibilityRule(
            id="legacy-remote-contracting",
            label=(
                "Remote work is suitable when the employer can contract "
                "Rafael from Spain or through his Irish limited company"
            ),
            terms=["remote"],
            outcome="eligible_with_conditions",
        )
    )

    assessment = calibrated_strategy_assessment(
        profile,
        title="Remote Data Annotator Jobs Barcelona",
        location="Barcelona, Catalonia, Spain",
        description="Remote role with advanced troubleshooting.",
    )

    assert assessment.eligibility == "eligible"
    assert not any(
        uncertainty.startswith("Remote work is suitable when the employer can contract ")
        for uncertainty in assessment.uncertainties
    )


def test_mixed_country_hybrid_with_explicit_spain_is_not_portugal_only(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer - Italy, Portugal, Spain (Hybrid)",
        location="Portugal",
        description="Advanced troubleshooting for enterprise customers.",
    )

    assert assessment.eligibility == "eligible_with_conditions"
    assert assessment.recommendation == "pursue_if_condition_met"
    assert not any(
        "vacancy is explicitly tied to Portugal" in blocker for blocker in assessment.blockers
    )
    assert any(
        "within the configured 30 km radius" in uncertainty
        for uncertainty in assessment.uncertainties
    )


def test_mixed_country_remote_with_explicit_spain_is_not_foreign_rejected(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer - Portugal / Spain (Remote)",
        location="Portugal",
        description="Advanced troubleshooting for enterprise customers.",
    )

    assert assessment.eligibility != "ineligible"
    assert not any(
        "vacancy is explicitly tied to Portugal" in blocker for blocker in assessment.blockers
    )


def test_incidental_spain_description_does_not_override_foreign_scope(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Portugal",
        description=(
            "Remote role based in Portugal. "
            "Provide troubleshooting support to customers in Spain and France."
        ),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"
    assert any(
        "vacancy is explicitly tied to Portugal" in blocker for blocker in assessment.blockers
    )


def test_maltese_speaker_requirement_is_blocked(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("Technical Analyst - Fully remote in Malta - Maltese speaker") == [
        "required language outside current preferences: maltese"
    ]


def test_work_from_anywhere_in_malta_is_not_worldwide_permission(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Analyst - Fully remote in Malta",
        location="Malta",
        description=(
            "Work from anywhere in Malta. Fully remote setup for employees located in Malta."
        ),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"
    assert any("vacancy is explicitly tied to Malta" in blocker for blocker in assessment.blockers)


def test_unscoped_work_from_anywhere_allows_cross_border_remote(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    profile = _profile()
    profile.eligibility_rules.append(
        EligibilityRule(
            id="legacy-remote-contracting",
            label=(
                "Remote work is suitable when the employer can contract "
                "Rafael from Spain or through his Irish limited company"
            ),
            terms=["remote", "work from anywhere"],
            outcome="eligible_with_conditions",
        )
    )

    assessment = calibrated_strategy_assessment(
        profile,
        title="System Administrator (Remote)",
        location="European Union",
        description=(
            "Location: Remote (Work from Anywhere). "
            "Manage cloud infrastructure and troubleshoot production systems."
        ),
    )

    assert assessment.eligibility == "eligible"
    assert not any(
        uncertainty.startswith("Remote work is suitable when the employer can contract ")
        for uncertainty in assessment.uncertainties
    )


def test_eu_based_only_remote_clears_legacy_contracting_uncertainty(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    profile = _profile()
    profile.eligibility_rules.append(
        EligibilityRule(
            id="legacy-remote-contracting",
            label=(
                "Remote work is suitable when the employer can contract "
                "Rafael from Spain or through his Irish limited company"
            ),
            terms=["remote", "work from anywhere"],
            outcome="eligible_with_conditions",
        )
    )

    assessment = calibrated_strategy_assessment(
        profile,
        title="Senior IT & Security Engineer",
        location="Germany",
        description=(
            "Remote-only company. You can work from a beach, a mountain, "
            "or your home office. We hire EU-based only for this role. "
            "Work from anywhere."
        ),
    )

    assert assessment.eligibility == "eligible"
    assert not any(
        uncertainty.startswith("Remote work is suitable when the employer can contract ")
        for uncertainty in assessment.uncertainties
    )


def test_preferred_maltese_speaker_is_not_blocked(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("Maltese speaker preferred; English is required.") == []


def test_fundraise_up_russian_requirement_is_hard_blocked(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    text = (
        "IT Support Engineer L2. "
        "Highlights: Location: Spain. "
        "Languages: Fluent in Russian and English. "
        "Working hours: 14:00 - 23:00 CET."
    )

    assert preference_blockers(text) == ["required language outside current preferences: russian"]


def test_swedish_speaking_requirement_is_blocked(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("IT Service Desk Technician (Swedish speaking)") == [
        "required language outside current preferences: swedish"
    ]


def test_czech_and_slovak_required_language_pair_is_blocked(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    blockers = preference_blockers("Excellent communication skills in Czech/Slovak and English.")

    assert "required language outside current preferences: czech" in blockers
    assert "required language outside current preferences: slovak" in blockers


def test_high_proficiency_czech_requirement_is_blocked(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("High proficiency in Czech and English, verbal and written.") == [
        "required language outside current preferences: czech"
    ]


def test_native_dutch_or_french_requirement_blocks_both_options(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    blockers = preference_blockers("You are a native Dutch and/or French speaker.")

    assert "required language outside current preferences: dutch" in blockers
    assert "required language outside current preferences: french" in blockers


def test_preferred_polish_and_german_are_not_required(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    text = "English C1 level is mandatory. German or Polish: strong advantage and preferred."

    assert preference_blockers(text) == []


def test_maltese_language_advantage_is_not_required(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("Maltese language skills are an advantage.") == []


def test_programming_languages_are_not_human_language_blockers(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("Fluent in Python, PowerShell and TypeScript.") == []


def test_required_russian_turns_viable_spain_role_ineligible(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="IT Support Engineer L2",
        location="Catalonia, Spain (Remote)",
        description=(
            "Languages: Fluent in Russian and English. "
            "L2 escalations, troubleshooting, SaaS administration, "
            "identity governance and incident response."
        ),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"
    assert any(
        "required language outside current preferences: russian" in blocker
        for blocker in assessment.blockers
    )


def test_simple_native_dutch_requirement_is_blocked(monkeypatch) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("Native Dutch required for customer communication.") == [
        "required language outside current preferences: dutch"
    ]


def test_native_language_requirement_does_not_depend_on_speaker_suffix(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("Native Dutch required for customer communication.") == [
        "required language outside current preferences: dutch"
    ]


def test_fluent_in_russian_and_english_blocks_russian(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("Languages: Fluent in Russian and English.") == [
        "required language outside current preferences: russian"
    ]


def test_optional_native_language_does_not_block(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("Native Dutch is preferred but not required.") == []


def test_language_advantage_does_not_inherit_required_marker(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assert preference_blockers("English is mandatory. Polish is an advantage.") == []


def test_source_first_nova_field_travel_is_ineligible(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical & Field Support Specialist II",
        location="Madrid, Spain · Remote",
        description=(
            "Remote technical support. Perform onsite installations. "
            "Travel to customer sites around Madrid area."
        ),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.fit_by_interview == 0


def test_source_first_remote_locality_restriction_is_ineligible(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Office 365 Support Administrator",
        location="Spain · Remote",
        description=(
            "100% remote. Only candidates from Sevilla, Málaga or nearby areas will be considered."
        ),
    )

    assert assessment.eligibility == "ineligible"


def test_source_first_mandatory_amos_is_ineligible(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Soporte Aplicativo con AMOS",
        location="Spain · Remote",
        description=("Requisito imprescindible: experiencia profesional con AMOS."),
    )

    assert assessment.eligibility == "ineligible"


def test_source_first_preferred_amos_is_not_blocked(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Application Support Specialist",
        location="Spain · Remote",
        description=(
            "AMOS experience preferred but not required. Troubleshoot enterprise applications."
        ),
    )

    assert not any("AMOS" in item for item in assessment.blockers)


def test_source_first_changegear_sunview_are_ineligible(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="SunView IT Operations Analyst",
        location="Spain · Remote",
        description=("Hands on experience with ChangeGear and SunView is required."),
    )

    assert assessment.eligibility == "ineligible"


def test_source_first_data_engineer_is_excluded(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Staff Data Engineer",
        location="Spain · Remote",
        description="Build data pipelines.",
    )

    assert assessment.recommendation == "do_not_pursue"
    assert assessment.fit_by_interview == 0


def test_source_first_workflex_engineer_not_excluded(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Senior IT & Security Engineer (AI-Native)",
        location="European Union · Remote",
        description=(
            "EU-based remote-only technical endpoint, identity and security engineering role."
        ),
    )

    assert not any("Source-first role eligibility" in item for item in assessment.blockers)


def test_source_first_degree_is_conditional(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Specialist II",
        location="Spain · Remote",
        description=(
            "Minimum BS or equivalent, in Chemistry, Biology, "
            "Medical Technology, Biomedical Engineering or Electronics."
        ),
    )

    assert assessment.eligibility == "eligible_with_conditions"
    assert assessment.recommendation == "pursue_if_condition_met"
    assert assessment.fit_by_interview <= 69


def test_source_first_large_experience_cannot_strong_pursue(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Cybersecurity Architect",
        location="Spain · Remote",
        description=(
            "Minimum 5 years of experience in perimeter-security architecture and design."
        ),
    )

    assert assessment.recommendation != "strong_pursue"
    assert assessment.fit_by_interview <= 69


def test_source_first_excluded_role_preserves_employment_eligibility(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Data Annotator",
        location="Barcelona, Catalonia, Spain",
        description=("Remote role based in Spain. Annotate data for an AI training project."),
    )

    assert assessment.eligibility == "eligible"
    assert assessment.recommendation == "do_not_pursue"
    assert assessment.fit_now == 0
    assert assessment.fit_by_interview == 0
    assert assessment.fit_on_the_job == 0
    assert any("Source-first career scope" in blocker for blocker in assessment.blockers)


def test_source_first_hybrid_infrastructure_is_not_work_mode(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Madrid, Community of Madrid, Spain",
        description=(
            "Support enterprise hybrid infrastructure, cloud services "
            "and network connectivity. "
            "The position does not state a workplace mode."
        ),
    )

    assert assessment.eligibility != "ineligible"
    assert not any(
        "Source-first location eligibility" in blocker for blocker in assessment.blockers
    )


def test_source_first_explicit_hybrid_role_still_counts_as_work_mode(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Madrid, Community of Madrid, Spain",
        description=("This is a hybrid role with regular attendance at the Madrid office."),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"


def test_source_first_hard_blocker_is_monotonic(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Senior Infrastructure Engineer",
        location="Poland",
        description=(
            "This vacancy is based in Poland. "
            "Minimum 6 years of experience in infrastructure engineering."
        ),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"
    assert any("Location eligibility" in blocker for blocker in assessment.blockers)
    assert any(
        "high-seniority experience requirement" in uncertainty
        for uncertainty in assessment.uncertainties
    )


def test_source_first_language_blocker_is_monotonic(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Spain · Remote",
        description=(
            "Fluent Czech is required. Minimum 5 years of experience in enterprise support."
        ),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"
    assert any(
        "required language outside current preferences: czech" in blocker
        for blocker in assessment.blockers
    )


def test_source_first_company_history_is_not_seniority_requirement(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Spain · Remote",
        description=(
            "Our company has over 35 years of experience "
            "delivering IT services worldwide. "
            "You will troubleshoot customer applications."
        ),
    )

    assert not any(
        "high-seniority experience requirement" in uncertainty
        for uncertainty in assessment.uncertainties
    )


def test_source_first_very_old_company_history_is_not_requirement(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Spain · Remote",
        description=(
            "With more than 90 years of experience in the field "
            "of public safety communication solutions, the company "
            "supports customers worldwide."
        ),
    )

    assert not any(
        "high-seniority experience requirement" in uncertainty
        for uncertainty in assessment.uncertainties
    )


def test_source_first_explicit_five_year_requirement_stays_conditional(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Technical Support Engineer",
        location="Spain · Remote",
        description=(
            "Minimum 5 years of experience in enterprise application support is required."
        ),
    )

    assert assessment.eligibility == "eligible_with_conditions"
    assert assessment.recommendation == "pursue_if_condition_met"
    assert any(
        "high-seniority experience requirement" in uncertainty
        for uncertainty in assessment.uncertainties
    )


def test_source_first_data_ops_engineer_is_excluded(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Data Ops Engineer + GenAI",
        location="Spain · Remote",
        description=(
            "60% Data / Analytics Engineering and 40% AI Enablement. Python, SQL and ETL/ELT."
        ),
    )

    assert assessment.recommendation == "do_not_pursue"
    assert assessment.fit_by_interview == 0


def test_source_first_data_science_specialist_is_excluded(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Data Science Specialist",
        location="Spain · Remote",
        description=("Build machine learning solutions, data models and data pipelines."),
    )

    assert assessment.recommendation == "do_not_pursue"
    assert assessment.fit_by_interview == 0


def test_source_first_data_ai_solutions_architect_is_excluded(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Senior Solutions Architect Data & AI en Azure",
        location="Spain · Remote",
        description=("Design modern data architectures, MLOps and generative AI platforms."),
    )

    assert assessment.recommendation == "do_not_pursue"
    assert assessment.fit_by_interview == 0


def test_source_first_spanish_locality_only_remote_is_ineligible(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Técnico de Administración y Soporte Office 365",
        location="Seville, Andalusia, Spain",
        description=(
            "Modalidad 100% remoto. "
            "Solo se valorarán candidaturas de Sevilla, "
            "Málaga o zonas cercanas."
        ),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"


def test_source_first_two_days_at_client_madrid_is_ineligible(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Soporte N1 Microsoft 365",
        location="Spain",
        description=(
            "Modalidad mixta. Aproximadamente 3 días de teletrabajo, "
            "2 días en cliente, Pozuelo de Alarcón (Madrid)."
        ),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"


def test_source_first_first_eight_weeks_madrid_is_ineligible(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Ingeniero SAP Sector Eléctrico",
        location="Madrid, Spain",
        description=(
            "La posición es 100% remoto, pero las primeras 8 semanas "
            "el candidato debe estar situado en las oficinas de Madrid."
        ),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"


def test_source_first_occasional_madrid_office_is_ineligible(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Especialista Técnico PL/SQL Unix",
        location="Madrid, Spain",
        description=(
            "Teletrabajo 100%. Disponibilidad para asistir "
            "puntualmente a oficinas situadas en Madrid."
        ),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"


def test_source_first_spanish_hps_prerequisite_is_ineligible(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Soporte N1 Microsoft 365",
        location="Spain · Remote",
        description=(
            "Requisito previo: Habilitación Personal de Seguridad HPS "
            "en tramitación o vigente antes de incorporación."
        ),
    )

    assert assessment.eligibility == "ineligible"
    assert assessment.recommendation == "do_not_pursue"
    assert any("clearance" in blocker.casefold() for blocker in assessment.blockers)


def test_excluded_family_body_text_cannot_hijack_technical_title(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    profile = _profile()

    assessment = calibrated_strategy_assessment(
        profile,
        title="Senior IT & Security Engineer (AI-Native)",
        location="European Union · Remote",
        description=(
            "Remote-only EU role. Build Entra ID, Microsoft 365, "
            "Intune, endpoint security and automation. "
            "You report directly to the Head of Technology."
        ),
    )

    assert assessment.role_family_id != "management"
    assert not any(
        "Pure Project / Product / People Management" in blocker for blocker in assessment.blockers
    )


def test_explicit_project_manager_title_remains_excluded(
    monkeypatch,
) -> None:
    _install_preferences(monkeypatch)

    assessment = calibrated_strategy_assessment(
        _profile(),
        title="IT Project Manager",
        location="Spain · Remote",
        description=("Coordinate technical teams and report to the Head of Technology."),
    )

    assert assessment.recommendation == "do_not_pursue"
