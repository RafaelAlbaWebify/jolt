from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ExperienceStatus = Literal[
    "confirmed_experience",
    "not_in_profile_yet",
    "unknown_ask_user",
    "confirmed_gap",
]
CredentialKind = Literal[
    "official_certification",
    "professional_certificate",
    "credential",
    "course",
    "cert_prep",
    "unknown",
]
MasterLanguage = Literal["en", "es"]
MasterFamily = Literal["application_support", "systems_automation"]


class CandidateSkillEvidence(BaseModel):
    skill: str = Field(min_length=1)
    status: ExperienceStatus = "confirmed_experience"
    source: str = "user_confirmed"


class CandidateCredential(BaseModel):
    name: str = Field(min_length=1)
    issuer: str = ""
    kind: CredentialKind = "unknown"


class CVMaster(BaseModel):
    language: MasterLanguage
    family: MasterFamily
    label: str = Field(min_length=1)


class CandidateEvidenceInventory(BaseModel):
    schema_version: str = "1.0"
    confirmed_skills: list[CandidateSkillEvidence] = Field(default_factory=list)
    linkedin_skills: list[str] = Field(default_factory=list)
    credentials: list[CandidateCredential] = Field(default_factory=list)
    expected_credential_count: int = 38
    credential_inventory_complete: bool = False
    credential_exclusions: list[str] = Field(default_factory=list)
    cv_masters: list[CVMaster] = Field(default_factory=list)


def _data_path() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / "data" / "candidate_evidence_inventory.json"


def _default_inventory() -> CandidateEvidenceInventory:
    confirmed = [
        "Windows Server",
        "Cisco servers",
        "Cisco switches",
        "WiFi",
        "macOS",
        "Linux",
        "Windows Registry",
        "Group Policy (GPO)",
        "Event Viewer",
        "MSI/EXE install switches",
        "Ivanti",
        "Intune",
        "Microsoft Defender",
        "Sophos",
        "ISO 27001",
        "GDPR",
        "license management",
        "subscription management",
        "inventory management",
        "cost management",
    ]
    return CandidateEvidenceInventory(
        confirmed_skills=[
            CandidateSkillEvidence(skill=skill, status="confirmed_experience")
            for skill in confirmed
        ],
        expected_credential_count=38,
        credential_inventory_complete=False,
        credential_exclusions=[
            "Azure Database Administrator Associate (DP-300) Cert Prep: 3 High Availability and Disaster Recovery in Azure Data Services",
        ],
        cv_masters=[
            CVMaster(
                language="en",
                family="application_support",
                label="Application Support master (EN)",
            ),
            CVMaster(
                language="es",
                family="application_support",
                label="Application Support master (ES)",
            ),
            CVMaster(
                language="en",
                family="systems_automation",
                label="Systems & Automation master (EN)",
            ),
            CVMaster(
                language="es",
                family="systems_automation",
                label="Systems & Automation master (ES)",
            ),
        ],
    )


def load_candidate_evidence_inventory() -> CandidateEvidenceInventory:
    path = _data_path()
    if not path.exists():
        return _default_inventory()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CandidateEvidenceInventory.model_validate(payload)
    except (json.JSONDecodeError, OSError, ValueError):
        return _default_inventory()


def save_candidate_evidence_inventory(
    inventory: CandidateEvidenceInventory,
) -> CandidateEvidenceInventory:
    path = _data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary_path.write_text(inventory.model_dump_json(indent=2), encoding="utf-8")
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return inventory
