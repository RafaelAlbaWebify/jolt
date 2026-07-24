from __future__ import annotations

import re
from pathlib import PurePosixPath

from pydantic import BaseModel
from sqlalchemy.orm import Session

from jolt.professional_intelligence_capture_runs import get_professional_capture_run

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

ARTIFACT_TYPES = {
    "screenshot_png": ".png",
    "rendered_text_json": ".json",
    "capture_metadata_json": ".json",
    "page_diagnostics_json": ".json",
}
PAGE_COMPLETENESS_STATUSES = ["complete", "partial", "failed"]
DEFAULT_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 365


class ProfessionalEvidencePolicy(BaseModel):
    allowed_artifact_types: list[str]
    page_completeness_statuses: list[str]
    default_retention_days: int
    maximum_retention_days: int
    text_extraction_policy: list[str]
    prohibited_evidence: list[str]


class ProfessionalExecutionReadiness(BaseModel):
    ready: bool = False
    execution_available: bool = False
    blockers: list[str]
    required_user_actions: list[str]
    evidence_policy: ProfessionalEvidencePolicy


class ProfessionalArtifactManifestEntry(BaseModel):
    capture_run_id: str
    source_id: str
    artifact_type: str
    relative_path: str
    sha256: str
    completeness_status: str
    retention_days: int = DEFAULT_RETENTION_DAYS


def professional_evidence_policy() -> ProfessionalEvidencePolicy:
    return ProfessionalEvidencePolicy(
        allowed_artifact_types=sorted(ARTIFACT_TYPES),
        page_completeness_statuses=PAGE_COMPLETENESS_STATUSES,
        default_retention_days=DEFAULT_RETENTION_DAYS,
        maximum_retention_days=MAX_RETENTION_DAYS,
        text_extraction_policy=[
            "visible_rendered_dom_text_is_primary",
            "ocr_is_fallback_only_when_dom_text_is_unavailable",
            "ocr_output_must_be_marked_as_derived",
            "screenshot_and_capture_metadata_must_link_to_each_text_artifact",
        ],
        prohibited_evidence=[
            "credentials",
            "cookies",
            "tokens",
            "browser_storage_state",
            "private_messages",
            "hidden_dom_content",
        ],
    )


def professional_execution_readiness() -> ProfessionalExecutionReadiness:
    return ProfessionalExecutionReadiness(
        blockers=[
            "supervised_browser_runner_not_implemented",
            "browser_session_boundary_not_configured",
            "local_evidence_root_not_verified",
            "explicit_per_run_user_confirmation_not_implemented",
        ],
        required_user_actions=[
            "choose_local_evidence_root",
            "start_each_capture_explicitly",
            "remain_present_during_capture",
            "review_artifacts_before_analysis",
        ],
        evidence_policy=professional_evidence_policy(),
    )


def validate_professional_artifact_manifest_entry(
    session: Session, entry: ProfessionalArtifactManifestEntry
) -> ProfessionalArtifactManifestEntry:
    run = get_professional_capture_run(session, entry.capture_run_id)
    planned_source_ids = {source.source_id for source in run.planned_sources}
    if entry.source_id not in planned_source_ids:
        raise ValueError("Artifact source must belong to the immutable run snapshot.")

    expected_extension = ARTIFACT_TYPES.get(entry.artifact_type)
    if expected_extension is None:
        raise ValueError("Unsupported Professional Intelligence artifact type.")

    path = PurePosixPath(entry.relative_path)
    expected_prefix = PurePosixPath(
        "professional-intelligence", entry.capture_run_id, entry.source_id
    )
    if path.is_absolute() or ".." in path.parts or path.parent != expected_prefix:
        raise ValueError("Artifact path must be a direct safe relative path under the run and source.")
    if path.suffix.lower() != expected_extension:
        raise ValueError("Artifact file extension does not match its declared type.")

    normalized_sha256 = entry.sha256.lower()
    if not _SHA256_PATTERN.fullmatch(normalized_sha256):
        raise ValueError("Artifact SHA-256 must contain exactly 64 hexadecimal characters.")

    if entry.completeness_status not in PAGE_COMPLETENESS_STATUSES:
        raise ValueError("Unsupported page completeness status.")
    if not 1 <= entry.retention_days <= MAX_RETENTION_DAYS:
        raise ValueError("Artifact retention must be between 1 and 365 days.")

    return entry.model_copy(update={"sha256": normalized_sha256})
