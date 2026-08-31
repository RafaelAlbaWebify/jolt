from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

WorkMode = Literal["remote", "hybrid", "onsite"]
ShiftPreference = Literal["business_hours", "flexible", "evening", "night", "rotating", "weekend"]
WorkloadPreference = Literal["normal", "high", "unknown"]

ALL_SHIFTS: list[ShiftPreference] = [
    "business_hours",
    "flexible",
    "evening",
    "night",
    "rotating",
    "weekend",
]

CURRENT_AI_REVIEW_POLICY_VERSION = "2026-08-31.3"


def _data_path() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / "data" / "job_search_preferences.json"


class JobSearchPreferences(BaseModel):
    target_titles: list[str] = Field(
        default_factory=lambda: [
            "Application Support Engineer",
            "Technical Support Engineer",
            "Software Support Engineer",
            "Production Support Engineer",
            "SaaS Support Engineer",
            "Enterprise Application Support",
        ]
    )
    preferred_work_modes: list[WorkMode] = Field(default_factory=lambda: ["remote", "hybrid"])
    base_locality: str = "Vigo, Galicia, Spain"
    max_hybrid_distance_km: int = Field(default=30, ge=0, le=500)
    relocation_allowed: bool = False
    countries: list[str] = Field(
        default_factory=lambda: ["Spain", "Ireland", "United Kingdom", "European Union"]
    )
    languages: list[str] = Field(default_factory=lambda: ["Spanish", "English"])
    language_certifications: list[str] = Field(default_factory=list)
    expected_salary_eur_min: int | None = Field(default=35000, ge=0, le=250000)
    expected_salary_eur_target: int | None = Field(default=45000, ge=0, le=250000)

    # Employment urgency takes precedence over shift comfort. Shift data may still
    # be reported by AI, but it must never act as an automatic rejection rule.
    preferred_shifts: list[ShiftPreference] = Field(default_factory=lambda: list(ALL_SHIFTS))
    excluded_shifts: list[ShiftPreference] = Field(default_factory=list)

    preferred_workload: WorkloadPreference = "normal"
    excluded_keywords: list[str] = Field(
        default_factory=lambda: ["dispatch", "field sales", "door to door", "commission only"]
    )
    preferred_keywords: list[str] = Field(
        default_factory=lambda: [
            "application support",
            "technical support",
            "sql",
            "logs",
            "api",
            "incident",
            "rca",
            "powershell",
        ]
    )

    # External AI review policy. These values are exported with every review pack
    # so an external reviewer does not have to infer eligibility rules from memory.
    review_policy_version: str = CURRENT_AI_REVIEW_POLICY_VERSION
    employment_urgency: Literal["normal", "high"] = "high"
    geography_policy: Literal["explicit_restrictions_only"] = "explicit_restrictions_only"
    direct_contact_before_apply: bool = False
    max_public_eligibility_check_minutes: int = Field(default=5, ge=0, le=30)
    learning_horizon_days: int = Field(default=14, ge=1, le=90)
    current_learning: list[str] = Field(
        default_factory=lambda: [
            "Microsoft Azure",
            "Microsoft Intune",
            "Entra ID",
            "endpoint management",
        ]
    )
    evaluation_policy_notes: str = (
        "A foreign listing location is neutral unless the vacancy explicitly restricts "
        "residency, work authorization, hiring region, citizenship, clearance, or requires "
        "physical work at a location outside the candidate's accepted commuting range. "
        "The candidate is not willing to relocate. A stated onsite workplace, client site, "
        "office attendance requirement, or assignment to a named distant physical workplace "
        "is positive geography evidence and must be treated as a hard blocker when it cannot "
        "be satisfied from the base locality. A remote scope such as 'Remote (USA)', 'remote "
        "within Germany', or an explicit country/region-only hiring statement is also positive "
        "geography evidence, not a neutral location label. Do not reject for shifts, unfamiliar "
        "tools, specialist technologies, seniority gaps, or role-family changes before AI "
        "evaluates transferability and learnability. A stated CEFR language level is a mandatory "
        "proficiency requirement; treat an official language certificate as mandatory only "
        "when the vacancy explicitly asks for certification, a certificate, or documentary proof. "
        "Do not require contacting an employer merely to determine basic eligibility before applying."
    )
    notes: str = (
        "Prioritize realistic applications quickly. Prefer remote or hybrid support work. The "
        "candidate will not relocate, so required distant onsite or client-site work is ineligible. "
        "Do not discard otherwise viable opportunities solely because of shifts or a foreign "
        "LinkedIn listing location."
    )

    @model_validator(mode="after")
    def enforce_employment_urgency_policy(self) -> JobSearchPreferences:
        """Normalize old saved preferences so deprecated blockers cannot return."""

        self.review_policy_version = CURRENT_AI_REVIEW_POLICY_VERSION
        self.excluded_shifts = []
        self.preferred_shifts = list(ALL_SHIFTS)
        self.employment_urgency = "high"
        self.geography_policy = "explicit_restrictions_only"
        self.direct_contact_before_apply = False
        self.relocation_allowed = False
        return self


def load_job_search_preferences() -> JobSearchPreferences:
    path = _data_path()
    if not path.exists():
        return JobSearchPreferences()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return JobSearchPreferences.model_validate(payload)
    except (json.JSONDecodeError, OSError, ValueError):
        return JobSearchPreferences()


def save_job_search_preferences(preferences: JobSearchPreferences) -> JobSearchPreferences:
    # Revalidate before persistence so stale UI clients cannot restore deprecated
    # shift exclusions, relocation, or the former geography policy.
    preferences = JobSearchPreferences.model_validate(preferences.model_dump())

    path = _data_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_suffix(path.suffix + ".tmp")

    try:
        temporary_path.write_text(
            preferences.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    return preferences
