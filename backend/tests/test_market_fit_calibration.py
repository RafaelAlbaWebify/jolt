import json
from datetime import UTC, datetime

from jolt.database import Evaluation, Posting
from jolt.evaluation_strategy import CapabilityAssessment, StrategyAssessment
from jolt.market_intelligence import _scope_data
from jolt.strategy_runtime import _remove_unsubstantiated_people_management_gap


def _posting(posting_id: str, title: str) -> Posting:
    return Posting(
        id=posting_id,
        source_document_id=f"source-{posting_id}",
        canonical_url=f"https://example.test/{posting_id}",
        identity_key=f"identity-{posting_id}",
        title=title,
        company="Example Company",
        location="Remote Spain",
        description="Provide incident, escalation and service management support.",
        identity_status="verified",
        created_at=datetime.now(UTC),
    )


def _evaluation(
    posting_id: str,
    *,
    recommendation: str,
    score: int,
    eligibility: str,
    gap_label: str,
    topic: str,
) -> Evaluation:
    assessment = {
        "eligibility": eligibility,
        "recommendation": recommendation,
        "gaps": [
            {
                "label": gap_label,
                "preparation_topics": [topic],
            }
        ],
    }
    return Evaluation(
        id=f"evaluation-{posting_id}",
        posting_id=posting_id,
        profile_version_id="profile:v1",
        engine_version="profile-rules-v4",
        recommendation=recommendation,
        confidence="high",
        ranking_score=score,
        reasons_json=json.dumps(
            ["Strategy assessment JSON: " + json.dumps(assessment, sort_keys=True)]
        ),
        created_at=datetime.now(UTC),
    )


def test_market_separates_technical_fit_from_actionable_decision() -> None:
    actionable = _posting("actionable", "Technical Support Engineer")
    blocked = _posting("blocked", "French-speaking Technical Support Engineer")
    data = _scope_data(
        [actionable, blocked],
        {
            actionable.id: _evaluation(
                actionable.id,
                recommendation="strong_pursue",
                score=90,
                eligibility="eligible",
                gap_label="Linux application support",
                topic="Practise Linux logs.",
            ),
            blocked.id: _evaluation(
                blocked.id,
                recommendation="do_not_pursue",
                score=95,
                eligibility="ineligible",
                gap_label="French language",
                topic="Study French.",
            ),
        },
    )

    assert data["strong_roles"] == 1
    assert data["blocked_roles"] == 1
    assert data["fit_distribution"] == [
        {"label": "Actionable strong match", "count": 1},
        {"label": "Actionable viable match", "count": 0},
        {"label": "Conditional / preparation needed", "count": 0},
        {"label": "Manual review needed", "count": 0},
        {"label": "Blocked / do not pursue", "count": 1},
    ]
    assert data["technical_fit_distribution"][0] == {
        "label": "Strong technical fit · 80–100",
        "count": 2,
    }
    assert data["top_gaps"] == [{"label": "Linux application support", "count": 1}]
    assert data["study_priorities"] == [{"label": "Practise Linux logs.", "count": 1}]


def _assessment_with_management_gap() -> StrategyAssessment:
    gap = CapabilityAssessment(
        capability_id="people-management",
        label="Formal people-management ownership",
        evidence_level=1,
        gap_type="preparable_in_1_to_3_months",
        matched_terms=("management",),
        preparation_topics=("Practise people-management scenarios.",),
    )
    return StrategyAssessment(
        eligibility="eligible",
        recommendation="pursue",
        confidence="high",
        role_family_id="technical-support",
        fit_now=75,
        fit_by_interview=83,
        fit_on_the_job=85,
        interview_days=10,
        estimated_preparation_hours=35,
        dimensions={
            "role_alignment": 100,
            "demonstrated_capability": 70,
            "transferable_capability": 60,
            "gap_feasibility": 80,
            "opportunity_quality": 50,
            "strategic_value": 80,
        },
        strengths=(),
        gaps=(gap,),
        blockers=(),
        uncertainties=(),
        preparation_plan=("Practise people-management scenarios.",),
    )


def test_support_titles_do_not_imply_people_management() -> None:
    titles = (
        "IT Support L3 (Relocation to Cyprus)",
        "Technical Support Specialist - night shifts",
        "IT Support Desk French Speaking",
    )
    for title in titles:
        result = _remove_unsubstantiated_people_management_gap(
            _assessment_with_management_gap(),
            title=title,
            location="Remote",
            description="Manage incidents, escalations and stakeholder communication.",
        )
        assert result.gaps == ()
        assert result.preparation_plan == ()


def test_explicit_staff_management_keeps_people_management_gap() -> None:
    original = _assessment_with_management_gap()
    result = _remove_unsubstantiated_people_management_gap(
        original,
        title="Technical Support Team Lead",
        location="Remote",
        description="Lead a team of 8 direct reports and conduct performance reviews.",
    )

    assert result is original
