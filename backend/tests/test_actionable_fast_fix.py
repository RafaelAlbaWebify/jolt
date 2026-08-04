from types import SimpleNamespace

from jolt import preference_aware_evaluation as preference_module
from jolt.job_search_preferences import JobSearchPreferences
from jolt.opportunity_index import OpportunityIndexItem, _opportunity_sort_key
from jolt.strategy_runtime import _actionable_ranking_score


def _preferences() -> JobSearchPreferences:
    return JobSearchPreferences(
        languages=["Spanish", "English"],
        excluded_shifts=["night", "rotating", "weekend"],
    )


def test_required_language_variants_are_blocked(monkeypatch) -> None:
    monkeypatch.setattr(
        preference_module,
        "load_job_search_preferences",
        _preferences,
    )

    examples = (
        "Deutschkenntnisse auf C1-Niveau sind erforderlich.",
        "Sehr gute Deutsch- und Englischkenntnisse in Wort und Schrift.",
        "Fluency in French and English, minimum B2 level.",
        "Italian speaking technical support specialist.",
    )

    for text in examples:
        blockers = preference_module.preference_blockers(text)
        assert any("required language outside current preferences" in item for item in blockers)


def test_country_restricted_remote_and_relocation_are_blocked(monkeypatch) -> None:
    monkeypatch.setattr(
        preference_module,
        "load_job_search_preferences",
        _preferences,
    )

    portugal = preference_module.preference_blockers(
        "Only for candidates already based in Portugal. Remote within Portugal."
    )
    cyprus = preference_module.preference_blockers(
        "This is an onsite role in Limassol and relocation to Cyprus is required."
    )

    assert "remote work is restricted to residence in another country" in portugal
    assert "relocation is required" in cyprus


def test_internship_temporary_and_foreign_onsite_are_blocked(monkeypatch) -> None:
    monkeypatch.setattr(
        preference_module,
        "load_job_search_preferences",
        _preferences,
    )

    internship = preference_module.preference_blockers("IT Support Internship")
    temporary = preference_module.preference_blockers(
        "Temporary role under Arbeitnehmerüberlassung."
    )
    onsite = preference_module.preference_blockers(
        "Germany remote listing. Vor Ort Installationen und Hardwaretausch."
    )

    assert "internship" in internship
    assert "temporary or fixed-term employment" in temporary
    assert "onsite duties are required outside the configured locality" in onsite


def test_actionable_score_is_zero_for_ineligible_and_capped_for_uncertain() -> None:
    assert (
        _actionable_ranking_score(
            SimpleNamespace(
                eligibility="ineligible",
                recommendation="do_not_pursue",
                fit_now=90,
                fit_by_interview=99,
            )
        )
        == 0
    )

    assert (
        _actionable_ranking_score(
            SimpleNamespace(
                eligibility="uncertain",
                recommendation="pursue_if_condition_met",
                fit_now=72,
                fit_by_interview=90,
            )
        )
        == 49
    )


def test_opportunity_index_orders_actionable_roles_before_blocked_roles() -> None:
    blocked = OpportunityIndexItem(
        posting_id="blocked",
        evaluation_id="evaluation-blocked",
        source_url="https://example.test/blocked",
        title="Blocked role",
        company="Example",
        location="Remote",
        recommendation="do_not_pursue",
        confidence="high",
        ranking_score=0,
    )
    viable = OpportunityIndexItem(
        posting_id="viable",
        evaluation_id="evaluation-viable",
        source_url="https://example.test/viable",
        title="Viable role",
        company="Example",
        location="Spain",
        recommendation="pursue",
        confidence="high",
        ranking_score=72,
    )
    strong = OpportunityIndexItem(
        posting_id="strong",
        evaluation_id="evaluation-strong",
        source_url="https://example.test/strong",
        title="Strong role",
        company="Example",
        location="Spain",
        recommendation="strong_pursue",
        confidence="high",
        ranking_score=85,
    )

    ordered = sorted([blocked, viable, strong], key=_opportunity_sort_key)
    assert [item.posting_id for item in ordered] == ["strong", "viable", "blocked"]
