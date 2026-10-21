from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

WorkMode = Literal["remote", "hybrid", "onsite"]
ShiftPreference = Literal["business_hours", "flexible", "evening", "night", "rotating", "weekend"]
WorkloadPreference = Literal["normal", "high", "unknown"]
LanguageLevel = Literal["basic", "conversational", "professional", "fluent", "native"]


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
            "Service Desk Analyst",
            "IT Coordinator",
            "Administrative Assistant",
            "Back Office Specialist",
            "Customer Support Specialist",
            "Service Coordinator",
            "Order Management Specialist",
        ]
    )
    preferred_work_modes: list[WorkMode] = Field(
        default_factory=lambda: ["remote", "hybrid", "onsite"]
    )
    base_locality: str = "Vigo, Galicia, Spain"
    max_hybrid_distance_km: int = Field(default=30, ge=0, le=500)
    countries: list[str] = Field(
        default_factory=lambda: ["Spain", "Ireland", "United Kingdom", "European Union"]
    )
    languages: list[str] = Field(default_factory=lambda: ["Spanish", "English"])
    language_levels: dict[str, LanguageLevel] = Field(
        default_factory=lambda: {
            "Spanish": "native",
            "English": "professional",
        }
    )
    expected_salary_eur_min: int | None = Field(default=17094, ge=0, le=250000)
    expected_salary_eur_target: int | None = Field(default=45000, ge=0, le=250000)
    preferred_shifts: list[ShiftPreference] = Field(
        default_factory=lambda: ["business_hours", "flexible"]
    )
    excluded_shifts: list[ShiftPreference] = Field(default_factory=list)
    preferred_workload: WorkloadPreference = "normal"
    excluded_keywords: list[str] = Field(
        default_factory=lambda: ["door to door", "commission only"]
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
    notes: str = (
        "Two-track search: primary IT and office-based bridge employment. "
        "Spanish 2026 full-time SMI is EUR 17094 gross per year; part-time "
        "pay is prorated. Prefer Vigo within 30 km for onsite/hybrid "
        "or genuinely Spain-eligible remote. Review physical demands "
        "and high-pressure sales. Preserve user-configured shift choices."
    )


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
