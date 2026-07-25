from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.professional_intelligence_capture_runs import get_professional_capture_run
from jolt.professional_intelligence_evidence_root import (
    get_professional_evidence_root,
    resolve_professional_evidence_path,
)
from jolt.professional_intelligence_records import ProfessionalCaptureArtifact

_REVIEWABLE_ARTIFACT_TYPES = {
    "rendered_text_json",
    "capture_metadata_json",
    "page_diagnostics_json",
}
_MAX_REVIEW_BYTES = 2_000_000


class ProfessionalEvidenceArtifactReview(BaseModel):
    id: str
    source_id: str
    artifact_type: str
    relative_path: str
    completeness_status: str
    retention_days: int
    exists: bool
    integrity_valid: bool
    reviewable: bool
    content: dict[str, object] | list[object] | str | None


class ProfessionalEvidenceSourceReview(BaseModel):
    source_id: str
    completeness_status: str
    artifacts: list[ProfessionalEvidenceArtifactReview]


class ProfessionalEvidenceRunReview(BaseModel):
    capture_run_id: str
    run_status: str
    integrity_valid: bool
    review_available: bool
    ready_for_analysis: bool
    sources: list[ProfessionalEvidenceSourceReview]


def _resolve_artifact_path(root_path: str, artifact: ProfessionalCaptureArtifact) -> Path:
    relative = PurePosixPath(artifact.relative_path)
    expected_parent = PurePosixPath(
        "professional-intelligence", artifact.capture_run_id, artifact.source_id
    )
    if relative.is_absolute() or ".." in relative.parts or relative.parent != expected_parent:
        raise ValueError("Stored artifact path is outside its immutable run/source scope.")
    return resolve_professional_evidence_path(
        str(Path(root_path) / "professional-intelligence"),
        artifact.capture_run_id,
        artifact.source_id,
        relative.name,
    )


def _review_content(path: Path, artifact_type: str) -> dict[str, object] | list[object] | str | None:
    if artifact_type not in _REVIEWABLE_ARTIFACT_TYPES or not path.is_file():
        return None
    if path.stat().st_size > _MAX_REVIEW_BYTES:
        raise ValueError("Reviewable evidence exceeds the 2 MB safety limit.")
    text = path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(parsed, (dict, list)):
        return parsed
    return str(parsed)


def review_professional_capture_evidence(
    session: Session, run_id: str
) -> ProfessionalEvidenceRunReview:
    run = get_professional_capture_run(session, run_id)
    evidence_root = get_professional_evidence_root(session)
    if not evidence_root.configured or not evidence_root.root_path:
        raise ValueError("A configured local evidence root is required for review.")

    artifacts = session.scalars(
        select(ProfessionalCaptureArtifact)
        .where(ProfessionalCaptureArtifact.capture_run_id == run_id)
        .order_by(
            ProfessionalCaptureArtifact.source_id,
            ProfessionalCaptureArtifact.artifact_type,
        )
    ).all()

    source_reviews: list[ProfessionalEvidenceSourceReview] = []
    all_integrity_valid = bool(artifacts)
    has_reviewable_text = False
    for source in run.planned_sources:
        source_artifacts = [artifact for artifact in artifacts if artifact.source_id == source.source_id]
        reviewed_artifacts: list[ProfessionalEvidenceArtifactReview] = []
        source_statuses: set[str] = set()
        for artifact in source_artifacts:
            path = _resolve_artifact_path(evidence_root.root_path, artifact)
            exists = path.is_file()
            integrity_valid = False
            if exists:
                integrity_valid = hashlib.sha256(path.read_bytes()).hexdigest() == artifact.sha256
            reviewable = artifact.artifact_type in _REVIEWABLE_ARTIFACT_TYPES
            content = _review_content(path, artifact.artifact_type) if integrity_valid else None
            if artifact.artifact_type == "rendered_text_json" and integrity_valid:
                has_reviewable_text = True
            all_integrity_valid = all_integrity_valid and exists and integrity_valid
            source_statuses.add(artifact.completeness_status)
            reviewed_artifacts.append(
                ProfessionalEvidenceArtifactReview(
                    id=artifact.id,
                    source_id=artifact.source_id,
                    artifact_type=artifact.artifact_type,
                    relative_path=artifact.relative_path,
                    completeness_status=artifact.completeness_status,
                    retention_days=artifact.retention_days,
                    exists=exists,
                    integrity_valid=integrity_valid,
                    reviewable=reviewable,
                    content=content,
                )
            )
        completeness = (
            "failed"
            if "failed" in source_statuses
            else "partial"
            if "partial" in source_statuses or not source_artifacts
            else "complete"
        )
        source_reviews.append(
            ProfessionalEvidenceSourceReview(
                source_id=source.source_id,
                completeness_status=completeness,
                artifacts=reviewed_artifacts,
            )
        )

    terminal = run.status in {"completed", "completed_with_gaps"}
    return ProfessionalEvidenceRunReview(
        capture_run_id=run_id,
        run_status=run.status,
        integrity_valid=all_integrity_valid,
        review_available=bool(artifacts),
        ready_for_analysis=terminal and all_integrity_valid and has_reviewable_text,
        sources=source_reviews,
    )
