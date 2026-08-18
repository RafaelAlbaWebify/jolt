from __future__ import annotations

from dataclasses import dataclass

from jolt.evaluation_strategy import (
    RoleFamily,
    StrategyAssessment,
    StrategyProfile,
    _fallback_role_bucket,
    _select_role_family,
)
from jolt.live_capture_workflow import _live_item_structure_failures
from jolt.schemas import LinkedInLiveCaptureItemRequest
from jolt.semantic_duplicates import group_semantic_duplicates
from jolt.strategy_runtime import (
    _calibrate_interview_uplift,
    _normalized_location_scope,
)


def _minimal_profile() -> StrategyProfile:
    return StrategyProfile(
        schema_version=1,
        profile_id="semantic-regression",
        version=1,
        role_families=[
            RoleFamily(
                id="it_operations",
                label="IT Operations",
                priority="primary",
                terms=["administrator"],
                strategic_value=80,
            ),
            RoleFamily(
                id="enterprise_application_support",
                label="Enterprise Application Support",
                priority="primary",
                terms=["application support"],
                strategic_value=90,
            ),
            RoleFamily(
                id="m365_identity",
                label="M365 Identity",
                priority="primary",
                terms=["entra id"],
                strategic_value=95,
            ),
        ],
        capabilities=[],
        eligibility_rules=[],
    )


def test_us_country_and_state_locations_are_foreign() -> None:
    assert _normalized_location_scope("United States") == "foreign_country"
    assert _normalized_location_scope("Dallas County, TX") == "foreign_country"
    assert _normalized_location_scope("New York, NY") == "foreign_country"
    assert _normalized_location_scope("Sarasota, FL") == "foreign_country"


def test_conditional_eligibility_cannot_remain_strong_pursue() -> None:
    assessment = StrategyAssessment(
        eligibility="eligible_with_conditions",
        recommendation="strong_pursue",
        confidence="high",
        role_family_id="it_operations",
        fit_now=90,
        fit_by_interview=95,
        fit_on_the_job=95,
        interview_days=10,
        estimated_preparation_hours=0,
        dimensions={},
        strengths=(),
        gaps=(),
        blockers=(),
        uncertainties=("Cross-border employment from Spain is not confirmed.",),
        preparation_plan=(),
    )

    calibrated = _calibrate_interview_uplift(assessment)

    assert calibrated.recommendation == "pursue_if_condition_met"
    assert calibrated.confidence == "low"


def test_common_support_and_operations_titles_have_fallback_families() -> None:
    assert _fallback_role_bucket("Support Analyst L2") == "support"
    assert _fallback_role_bucket("Helpdesk Technician II") == "support"
    assert _fallback_role_bucket("Escalation Engineer (Tier 3 Support)") == "support"
    assert _fallback_role_bucket("Technical Consultant remote USA") == "support"
    assert _fallback_role_bucket("Tier 1 Engineer, Network Operations Center") == "operations"
    assert _fallback_role_bucket("System Administrator II") == "operations"
    assert _fallback_role_bucket("Staff Systems Engineer, IT") == "operations"
    assert _fallback_role_bucket("IT & Operations Specialist") == "operations"


def test_microsoft_365_title_prefers_m365_family() -> None:
    family = _select_role_family(
        _minimal_profile(),
        title="Microsoft 365 Administrator",
        location="Remote Spain",
        description="Administer Microsoft cloud services and user access.",
    )

    assert family is not None
    assert family.id == "m365_identity"


def test_live_capture_rejects_description_prose_in_company_field() -> None:
    evidence = LinkedInLiveCaptureItemRequest(
        source_job_id="4445359749",
        source_url="https://www.linkedin.com/jobs/view/4445359749",
        title="Senior Information Technology Specialist",
        company=" ".join(["This is job description prose"] * 100),
        location="",
        description="Provide enterprise IT support and systems administration.",
        identity_verified=True,
        verification_reason="Detail identity matched.",
    )

    failures = _live_item_structure_failures(evidence)

    assert failures
    assert any("company field" in failure for failure in failures)


@dataclass
class Candidate:
    posting_id: str
    company: str
    title: str
    recommendation: str = "pursue"
    confidence: str = "high"
    ranking_score: int = 75


def test_near_identical_aggregator_reposts_group_across_company_labels() -> None:
    first = Candidate(
        posting_id="facet",
        company="Facet",
        title="Technology Operations Support Analyst",
    )
    second = Candidate(
        posting_id="swooped",
        company="Swooped",
        title="Technology Operations Support Analyst",
    )

    shared = " ".join(
        [
            "Provide technology operations support",
            "troubleshoot Windows and SaaS incidents",
            "manage user access and service requests",
            "document resolutions and escalate production issues",
        ]
        * 40
    )

    descriptions = {
        "facet": shared,
        "swooped": shared + " Apply through the recruiting partner.",
    }

    groups = group_semantic_duplicates(
        [first, second],
        descriptions=descriptions,
    )

    assert len(groups) == 1
    assert {candidate.posting_id for candidate in groups[0]} == {
        "facet",
        "swooped",
    }


def test_different_companies_with_only_generic_similarity_remain_separate() -> None:
    first = Candidate(
        posting_id="one",
        company="Company One",
        title="Technical Support Engineer",
    )
    second = Candidate(
        posting_id="two",
        company="Company Two",
        title="Technical Support Engineer",
    )

    descriptions = {
        "one": (
            "Support payroll SaaS users, investigate HR integrations, "
            "employee records and benefits workflows."
        ),
        "two": (
            "Support industrial control systems, PLC communications, "
            "factory networks and production machinery."
        ),
    }

    groups = group_semantic_duplicates(
        [first, second],
        descriptions=descriptions,
    )

    assert len(groups) == 2
