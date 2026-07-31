from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

WorkMode = Literal["remote", "hybrid", "onsite"]
ShiftPreference = Literal["business_hours", "flexible", "evening", "night", "rotating", "weekend"]
WorkloadPreference = Literal["normal", "high", "unknown"]


def _data_path() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    data_dir = backend_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "job_search_preferences.json"


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
    max_hybrid_distance_km: int = Field(default=60, ge=0, le=500)
    countries: list[str] = Field(default_factory=lambda: ["Spain", "Ireland", "United Kingdom", "European Union"])
    languages: list[str] = Field(default_factory=lambda: ["Spanish", "English"])
    expected_salary_eur_min: int | None = Field(default=35000, ge=0, le=250000)
    expected_salary_eur_target: int | None = Field(default=45000, ge=0, le=250000)
    preferred_shifts: list[ShiftPreference] = Field(default_factory=lambda: ["business_hours", "flexible"])
    excluded_shifts: list[ShiftPreference] = Field(default_factory=lambda: ["night", "rotating", "weekend"])
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
    notes: str = "Prefer stable remote or hybrid support roles that bridge IT operations and application/software support. Avoid irrelevant dispatch-style work."


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
    path.write_text(preferences.model_dump_json(indent=2), encoding="utf-8")
    return preferences
