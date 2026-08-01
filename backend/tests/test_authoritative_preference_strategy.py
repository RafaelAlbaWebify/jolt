from jolt.evaluation_strategy import StrategyAssessment
from jolt.strategy_runtime import ENGINE_VERSION, _apply_saved_preferences


def _assessment() -> StrategyAssessment:
    return StrategyAssessment(
        eligibility="eligible",
        recommendation="pursue",
        confidence="medium",
        role_family_id="technical-support",
        fit_now=70,
        fit_by_interview=78,
        fit_on_the_job=82,
        interview_days=10,
        estimated_preparation_hours=4,
        dimensions={
            "role_alignment": 100,
            "demonstrated_capability": 70,
            "transferable_capability": 60,
            "gap_feasibility": 100,
            "opportunity_quality": 50,
            "strategic_value": 80,
        },
        strengths=("Support experience.",),
        gaps=(),
        blockers=(),
        uncertainties=(),
        preparation_plan=(),
    )


def test_strategy_engine_version_is_preference_aware_v5() -> None:
    assert ENGINE_VERSION == "profile-rules-v5"


def test_strategy_keeps_assessment_when_current_preferences_do_not_block(monkeypatch) -> None:
    from jolt import strategy_runtime

    original = _assessment()
    monkeypatch.setattr(strategy_runtime, "preference_blockers", lambda _text: [])

    result = _apply_saved_preferences(
        original,
        title="Technical Support Engineer - night shifts",
        location="Remote Spain",
        description="SQL and API support",
    )

    assert result is original
    assert result.recommendation == "pursue"
    assert result.eligibility == "eligible"


def test_strategy_rejects_only_an_explicit_saved_preference_blocker(monkeypatch) -> None:
    from jolt import strategy_runtime

    monkeypatch.setattr(
        strategy_runtime,
        "preference_blockers",
        lambda _text: ["required language outside current preferences: french"],
    )

    result = _apply_saved_preferences(
        _assessment(),
        title="French-speaking Technical Support Engineer",
        location="Remote Spain",
        description="SQL and API support",
    )

    assert result.recommendation == "do_not_pursue"
    assert result.eligibility == "ineligible"
    assert result.confidence == "high"
    assert result.fit_by_interview == 78
    assert result.blockers == (
        "Job-search preference: required language outside current preferences: french.",
    )
