from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

EvidenceLevel = Literal[0, 1, 2, 3, 4, 5]
RolePriority = Literal["primary", "secondary", "opportunistic", "excluded"]
Recommendation = Literal[
    "strong_pursue",
    "pursue",
    "pursue_if_condition_met",
    "review_manually",
    "defer",
    "do_not_pursue",
]
GapType = Literal[
    "ready_now",
    "preparable_in_days",
    "preparable_in_1_to_2_weeks",
    "preparable_in_1_to_3_months",
    "experience_gap",
    "fundamental_mismatch",
    "unknown",
]


class CapabilityEvidence(BaseModel):
    id: str
    label: str
    terms: list[str]
    evidence_level: EvidenceLevel
    transferable_to: list[str] = Field(default_factory=list)
    preparation_topics: list[str] = Field(default_factory=list)


class RoleFamily(BaseModel):
    id: str
    label: str
    priority: RolePriority
    terms: list[str]
    strategic_value: int = Field(default=50, ge=0, le=100)


class EligibilityRule(BaseModel):
    id: str
    label: str
    terms: list[str]
    outcome: Literal["eligible_with_conditions", "uncertain", "ineligible"]


class PreparationCapacity(BaseModel):
    hours_per_week: int = Field(default=10, ge=0, le=80)
    default_days_until_technical: int = Field(default=10, ge=0, le=90)
    ai_guided_study: bool = True
    documentation: bool = True
    labs: bool = False
    mock_interviews: bool = True
    maximum_parallel_processes: int = Field(default=3, ge=1, le=20)


class EvaluationWeights(BaseModel):
    role_alignment: int = Field(default=20, ge=0, le=100)
    demonstrated_capability: int = Field(default=25, ge=0, le=100)
    transferable_capability: int = Field(default=10, ge=0, le=100)
    gap_feasibility: int = Field(default=15, ge=0, le=100)
    opportunity_quality: int = Field(default=15, ge=0, le=100)
    strategic_value: int = Field(default=15, ge=0, le=100)

    @model_validator(mode="after")
    def weights_total_one_hundred(self) -> EvaluationWeights:
        if sum(self.model_dump().values()) != 100:
            raise ValueError("Evaluation weights must total 100.")
        return self


class StrategyProfile(BaseModel):
    schema_version: Literal[1] = 1
    profile_id: str
    version: int = Field(ge=1)
    display_name: str = "Local JOLT user"
    role_families: list[RoleFamily]
    capabilities: list[CapabilityEvidence]
    eligibility_rules: list[EligibilityRule] = Field(default_factory=list)
    preparation: PreparationCapacity = Field(default_factory=PreparationCapacity)
    weights: EvaluationWeights = Field(default_factory=EvaluationWeights)

    @property
    def version_id(self) -> str:
        return f"{self.profile_id}:v{self.version}"


@dataclass(frozen=True)
class CapabilityAssessment:
    capability_id: str
    label: str
    evidence_level: int
    gap_type: GapType
    matched_terms: tuple[str, ...]
    preparation_topics: tuple[str, ...]


@dataclass(frozen=True)
class StrategyAssessment:
    eligibility: str
    recommendation: Recommendation
    confidence: str
    role_family_id: str | None
    fit_now: int
    fit_by_interview: int
    fit_on_the_job: int
    interview_days: int
    estimated_preparation_hours: int
    dimensions: dict[str, int]
    strengths: tuple[str, ...]
    gaps: tuple[CapabilityAssessment, ...]
    blockers: tuple[str, ...]
    uncertainties: tuple[str, ...]
    preparation_plan: tuple[str, ...]


def default_profile_path() -> Path:
    configured = os.getenv("JOLT_PROFILE_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    repository_root = Path(__file__).resolve().parents[3]
    return repository_root / ".jolt" / "profiles" / "active.private.json"


def load_strategy_profile(path: Path | None = None) -> StrategyProfile:
    profile_path = path or default_profile_path()
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    return StrategyProfile.model_validate(payload)


def _matched_terms(text: str, terms: list[str]) -> tuple[str, ...]:
    return tuple(term for term in terms if term.lower() in text)


def _gap_type(evidence_level: int) -> GapType:
    return {
        5: "ready_now",
        4: "ready_now",
        3: "preparable_in_days",
        2: "preparable_in_1_to_2_weeks",
        1: "preparable_in_1_to_3_months",
        0: "experience_gap",
    }[evidence_level]


def _capability_score(level: int) -> int:
    return {0: 0, 1: 15, 2: 35, 3: 60, 4: 82, 5: 100}[level]


def _preparation_hours(gap_type: GapType) -> int:
    return {
        "ready_now": 0,
        "preparable_in_days": 4,
        "preparable_in_1_to_2_weeks": 10,
        "preparable_in_1_to_3_months": 35,
        "experience_gap": 120,
        "fundamental_mismatch": 240,
        "unknown": 20,
    }[gap_type]


def _average(values: list[int], default: int = 0) -> int:
    return round(sum(values) / len(values)) if values else default


def assess_posting(
    profile: StrategyProfile,
    title: str,
    location: str,
    description: str,
    *,
    days_until_technical: int | None = None,
) -> StrategyAssessment:
    text = "\n".join([title, location, description]).lower()
    interview_days = (
        profile.preparation.default_days_until_technical
        if days_until_technical is None
        else max(0, days_until_technical)
    )

    blockers: list[str] = []
    uncertainties: list[str] = []
    eligibility = "eligible"
    for rule in profile.eligibility_rules:
        matches = _matched_terms(text, rule.terms)
        if not matches:
            continue
        message = f"{rule.label}: {', '.join(matches)}."
        if rule.outcome == "ineligible":
            blockers.append(message)
            eligibility = "ineligible"
        elif rule.outcome == "uncertain" and eligibility != "ineligible":
            uncertainties.append(message)
            eligibility = "uncertain"
        elif eligibility == "eligible":
            uncertainties.append(message)
            eligibility = "eligible_with_conditions"

    role_matches = [
        (family, _matched_terms(text, family.terms))
        for family in profile.role_families
        if _matched_terms(text, family.terms)
    ]
    role_family = role_matches[0][0] if role_matches else None
    role_alignment = {
        "primary": 100,
        "secondary": 75,
        "opportunistic": 50,
        "excluded": 0,
    }.get(role_family.priority if role_family else "", 25)
    if role_family and role_family.priority == "excluded":
        blockers.append(f"Excluded role family: {role_family.label}.")

    capability_results: list[CapabilityAssessment] = []
    for capability in profile.capabilities:
        matches = _matched_terms(text, capability.terms)
        if not matches:
            continue
        capability_results.append(
            CapabilityAssessment(
                capability_id=capability.id,
                label=capability.label,
                evidence_level=capability.evidence_level,
                gap_type=_gap_type(capability.evidence_level),
                matched_terms=matches,
                preparation_topics=tuple(capability.preparation_topics),
            )
        )

    demonstrated = _average(
        [_capability_score(item.evidence_level) for item in capability_results], default=20
    )
    transferable = _average(
        [
            min(100, _capability_score(capability.evidence_level) + 10)
            for capability in profile.capabilities
            if capability.transferable_to
            and _matched_terms(text, capability.transferable_to)
        ],
        default=25,
    )

    required_hours = sum(_preparation_hours(item.gap_type) for item in capability_results)
    available_hours = round(profile.preparation.hours_per_week * interview_days / 7)
    preparation_feasibility = 100 if required_hours == 0 else min(100, available_hours * 100 // required_hours)
    opportunity_quality = 50
    strategic_value = role_family.strategic_value if role_family else 35

    dimensions = {
        "role_alignment": role_alignment,
        "demonstrated_capability": demonstrated,
        "transferable_capability": transferable,
        "gap_feasibility": preparation_feasibility,
        "opportunity_quality": opportunity_quality,
        "strategic_value": strategic_value,
    }
    weights = profile.weights.model_dump()
    fit_now = round(sum(dimensions[key] * weights[key] for key in weights) / 100)

    preparable = [
        item
        for item in capability_results
        if item.gap_type in {"preparable_in_days", "preparable_in_1_to_2_weeks"}
    ]
    interview_uplift = min(
        25,
        round(preparation_feasibility * len(preparable) / max(1, len(capability_results)) / 4),
    )
    fit_by_interview = min(100, fit_now + interview_uplift)
    fit_on_the_job = min(100, max(fit_by_interview, round((fit_by_interview + strategic_value) / 2)))

    if eligibility == "ineligible" or (role_family and role_family.priority == "excluded"):
        recommendation: Recommendation = "do_not_pursue"
    elif fit_by_interview >= 80 and fit_now >= 70:
        recommendation = "strong_pursue"
    elif fit_by_interview >= 70:
        recommendation = "pursue"
    elif fit_by_interview >= 58 and preparation_feasibility >= 60:
        recommendation = "pursue_if_condition_met"
    elif uncertainties:
        recommendation = "review_manually"
    elif fit_by_interview >= 45:
        recommendation = "defer"
    else:
        recommendation = "do_not_pursue"

    confidence = "high" if role_family and capability_results else "medium"
    if not role_family or not capability_results:
        confidence = "low"

    strengths = tuple(
        f"{item.label}: evidence level {item.evidence_level}; matched {', '.join(item.matched_terms)}."
        for item in capability_results
        if item.evidence_level >= 3
    )
    gaps = tuple(item for item in capability_results if item.evidence_level < 4)
    preparation_plan = tuple(
        topic
        for item in gaps
        if item.gap_type in {"preparable_in_days", "preparable_in_1_to_2_weeks"}
        for topic in item.preparation_topics
    )

    return StrategyAssessment(
        eligibility=eligibility,
        recommendation=recommendation,
        confidence=confidence,
        role_family_id=role_family.id if role_family else None,
        fit_now=fit_now,
        fit_by_interview=fit_by_interview,
        fit_on_the_job=fit_on_the_job,
        interview_days=interview_days,
        estimated_preparation_hours=required_hours,
        dimensions=dimensions,
        strengths=strengths,
        gaps=gaps,
        blockers=tuple(blockers),
        uncertainties=tuple(uncertainties),
        preparation_plan=preparation_plan,
    )
