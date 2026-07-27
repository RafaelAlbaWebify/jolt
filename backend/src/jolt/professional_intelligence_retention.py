from __future__ import annotations

from datetime import timedelta
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import utc_now
from jolt.professional_intelligence_evidence_root import get_professional_evidence_root
from jolt.professional_intelligence_records import ProfessionalCaptureArtifact

RETENTION_CLEANUP_CONFIRMATION_PHRASE = "DELETE EXPIRED PROFESSIONAL EVIDENCE"


class ProfessionalRetentionCandidate(BaseModel):
    artifact_id: str
    capture_run_id: str
    source_id: str
    artifact_type: str
    relative_path: str
    created_at: str
    expires_at: str
    retention_days: int
    existing_bytes: int = Field(ge=0)


class ProfessionalRetentionPreview(BaseModel):
    generated_at: str
    confirmation_phrase: str
    expired_artifact_count: int = Field(ge=0)
    existing_file_count: int = Field(ge=0)
    existing_bytes: int = Field(ge=0)
    candidates: list[ProfessionalRetentionCandidate]


class ProfessionalRetentionCleanupRequest(BaseModel):
    confirmation_phrase: str


class ProfessionalRetentionCleanupResult(BaseModel):
    completed_at: str
    deleted_artifact_count: int = Field(ge=0)
    deleted_file_count: int = Field(ge=0)
    deleted_bytes: int = Field(ge=0)


def _professional_root(session: Session) -> Path:
    evidence_root = get_professional_evidence_root(session)
    if not (
        evidence_root.configured
        and evidence_root.root_path
        and evidence_root.exists
        and evidence_root.writable
    ):
        raise ValueError("A verified writable local evidence root is required.")
    root = (Path(evidence_root.root_path) / "professional-intelligence").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _artifact_path(professional_root: Path, relative_path: str) -> Path:
    relative = PurePosixPath(relative_path)
    if not relative.parts or relative.parts[0] != "professional-intelligence":
        raise ValueError("Artifact path is outside the professional evidence namespace.")
    path = (professional_root.parent / Path(*relative.parts)).resolve()
    if not path.is_relative_to(professional_root):
        raise ValueError("Artifact path escapes the configured professional evidence root.")
    return path


def _expired_artifacts(session: Session) -> list[ProfessionalCaptureArtifact]:
    now = utc_now()
    artifacts = session.scalars(select(ProfessionalCaptureArtifact)).all()
    return [
        artifact
        for artifact in artifacts
        if artifact.created_at + timedelta(days=artifact.retention_days) <= now
    ]


def preview_professional_retention_cleanup(session: Session) -> ProfessionalRetentionPreview:
    professional_root = _professional_root(session)
    now = utc_now()
    candidates: list[ProfessionalRetentionCandidate] = []
    existing_file_count = 0
    existing_bytes = 0

    for artifact in _expired_artifacts(session):
        final_path = _artifact_path(professional_root, artifact.relative_path)
        staged_path = final_path.with_name(f"{final_path.name}.staged")
        artifact_bytes = 0
        for path in (final_path, staged_path):
            if path.is_file():
                artifact_bytes += path.stat().st_size
                existing_file_count += 1
        existing_bytes += artifact_bytes
        candidates.append(
            ProfessionalRetentionCandidate(
                artifact_id=artifact.id,
                capture_run_id=artifact.capture_run_id,
                source_id=artifact.source_id,
                artifact_type=artifact.artifact_type,
                relative_path=artifact.relative_path,
                created_at=artifact.created_at.isoformat(),
                expires_at=(
                    artifact.created_at + timedelta(days=artifact.retention_days)
                ).isoformat(),
                retention_days=artifact.retention_days,
                existing_bytes=artifact_bytes,
            )
        )

    candidates.sort(key=lambda candidate: (candidate.expires_at, candidate.relative_path))
    return ProfessionalRetentionPreview(
        generated_at=now.isoformat(),
        confirmation_phrase=RETENTION_CLEANUP_CONFIRMATION_PHRASE,
        expired_artifact_count=len(candidates),
        existing_file_count=existing_file_count,
        existing_bytes=existing_bytes,
        candidates=candidates,
    )


def cleanup_expired_professional_evidence(
    session: Session,
    request: ProfessionalRetentionCleanupRequest,
) -> ProfessionalRetentionCleanupResult:
    if request.confirmation_phrase != RETENTION_CLEANUP_CONFIRMATION_PHRASE:
        raise ValueError("The exact retention cleanup confirmation phrase is required.")

    professional_root = _professional_root(session)
    expired = _expired_artifacts(session)
    deleted_file_count = 0
    deleted_bytes = 0

    try:
        for artifact in expired:
            final_path = _artifact_path(professional_root, artifact.relative_path)
            staged_path = final_path.with_name(f"{final_path.name}.staged")
            for path in (final_path, staged_path):
                if path.is_file():
                    deleted_bytes += path.stat().st_size
                    path.unlink()
                    deleted_file_count += 1
            session.delete(artifact)
        session.commit()
    except Exception:
        session.rollback()
        raise

    for path in sorted(professional_root.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass

    return ProfessionalRetentionCleanupResult(
        completed_at=utc_now().isoformat(),
        deleted_artifact_count=len(expired),
        deleted_file_count=deleted_file_count,
        deleted_bytes=deleted_bytes,
    )
