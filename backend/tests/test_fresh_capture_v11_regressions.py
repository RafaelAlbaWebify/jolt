from __future__ import annotations

import json
from pathlib import Path

import pytest

from jolt.evaluation_strategy import (
    CapabilityEvidence,
    RoleFamily,
    StrategyProfile,
)
from jolt.job_search_preferences import JobSearchPreferences
from jolt.strategy_runtime import calibrated_strategy_assessment

_FIXTURE = Path(__file__).parent / "fixtures" / "fresh_capture_v11_20260825.json"


def _jobs() -> dict[str, dict[str, str]]:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return {job["source_job_id"]: job for job in payload["jobs"]}


JOBS = _jobs()


def _preferences() -> JobSearchPreferences:
    """
    Stable public search intent.

    These preferences deliberately do not depend on the developer's local
    backend/data/job_search_preferences.json file.
    """
    return JobSearchPreferences(
        countries=[
            "Spain",
            "Ireland",
            "United Kingdom",
            "European Union",
        ],
        languages=["Spanish", "English"],
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


def _permissive_technical_profile() -> StrategyProfile:
    """
    Synthetic profile used to isolate hard blockers.

    It intentionally gives broad technical/Dynamics wording a favorable
    baseline. The tests therefore verify that an otherwise attractive role
    is still rejected when source evidence proves geography or career scope
    incompatible.
    """
    return StrategyProfile(
        profile_id="v11-public-regression",
        version=1,
        role_families=[
            RoleFamily(
                id="permissive_technical",
                label="Permissive technical baseline",
                priority="primary",
                terms=[
                    "dynamics",
                    "microsoft",
                    "application",
                    "support",
                    "customer",
                    "solution",
                    "technical",
                ],
                strategic_value=95,
            ),
        ],
        capabilities=[
            CapabilityEvidence(
                id="technical_delivery",
                label="Technical delivery",
                terms=[
                    "support",
                    "implementation",
                    "design",
                    "documentation",
                    "troubleshoot",
                    "integration",
                ],
                evidence_level=5,
            ),
            CapabilityEvidence(
                id="automation_integration",
                label="Automation and integration",
                terms=[
                    "automation",
                    "api",
                    "rest",
                    "json",
                    "integration",
                ],
                evidence_level=4,
            ),
            CapabilityEvidence(
                id="customer_work",
                label="Customer-facing technical work",
                terms=[
                    "customer",
                    "client",
                    "business requirements",
                ],
                evidence_level=4,
            ),
        ],
    )


@pytest.mark.parametrize(
    "source_job_id",
    [
        "4458281459",  # Nortal / Brazil + LATAM remote
        "4457058425",  # BDO Edmonton / anywhere in Canada
        "4457073327",  # BDO Calgary / anywhere in Canada
    ],
)
def test_fresh_capture_foreign_remote_scope_is_hard_rejected(
    monkeypatch,
    source_job_id: str,
) -> None:
    _install_preferences(monkeypatch)

    job = JOBS[source_job_id]

    assessment = calibrated_strategy_assessment(
        _permissive_technical_profile(),
        title=job["title"],
        location=job["location"],
        description=job["description"],
    )

    assert assessment.recommendation == "do_not_pursue", (
        f"{job['company']} / LinkedIn {source_job_id}: "
        f"foreign employment scope must hard reject; "
        f"got recommendation={assessment.recommendation}, "
        f"eligibility={assessment.eligibility}, "
        f"blockers={assessment.blockers}, "
        f"uncertainties={assessment.uncertainties}"
    )

    assert any("Location eligibility:" in blocker for blocker in assessment.blockers), (
        f"{job['company']} / LinkedIn {source_job_id}: "
        f"expected an explicit location blocker; "
        f"got {assessment.blockers}"
    )


@pytest.mark.parametrize(
    "source_job_id",
    [
        "4449558187",  # Dynamics / Power Platform Developer, 4+ years
        "4456869907",  # Senior Dynamics CRM consultant/developer
        "4458187422",  # Dynamics CRM Solution Architect
    ],
)
def test_fresh_capture_specialist_role_scope_is_hard_rejected(
    monkeypatch,
    source_job_id: str,
) -> None:
    _install_preferences(monkeypatch)

    job = JOBS[source_job_id]

    assessment = calibrated_strategy_assessment(
        _permissive_technical_profile(),
        title=job["title"],
        location=job["location"],
        description=job["description"],
    )

    assert assessment.recommendation == "do_not_pursue", (
        f"{job['company']} / LinkedIn {source_job_id}: "
        f"specialist career scope must hard reject; "
        f"got recommendation={assessment.recommendation}, "
        f"eligibility={assessment.eligibility}, "
        f"role_family={assessment.role_family_id}, "
        f"blockers={assessment.blockers}, "
        f"uncertainties={assessment.uncertainties}"
    )
