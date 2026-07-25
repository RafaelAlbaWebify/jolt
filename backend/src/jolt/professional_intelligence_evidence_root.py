from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.orm import Session

from jolt.database import utc_now
from jolt.professional_intelligence_records import ProfessionalEvidenceSettings

_SETTINGS_ID = "professional-evidence"


class ProfessionalEvidenceRootRequest(BaseModel):
    root_path: str


class ProfessionalEvidenceRootResponse(BaseModel):
    configured: bool
    root_path: str | None
    exists: bool
    writable: bool
    verified_at: str | None


def _response(settings: ProfessionalEvidenceSettings | None) -> ProfessionalEvidenceRootResponse:
    if settings is None:
        return ProfessionalEvidenceRootResponse(
            configured=False,
            root_path=None,
            exists=False,
            writable=False,
            verified_at=None,
        )
    path = Path(settings.root_path)
    return ProfessionalEvidenceRootResponse(
        configured=True,
        root_path=str(path),
        exists=path.is_dir(),
        writable=path.is_dir() and os.access(path, os.W_OK),
        verified_at=settings.verified_at.isoformat(),
    )


def get_professional_evidence_root(session: Session) -> ProfessionalEvidenceRootResponse:
    return _response(session.get(ProfessionalEvidenceSettings, _SETTINGS_ID))


def configure_professional_evidence_root(
    session: Session, request: ProfessionalEvidenceRootRequest
) -> ProfessionalEvidenceRootResponse:
    raw_path = request.root_path.strip()
    if not raw_path:
        raise ValueError("A local evidence directory is required.")
    path = Path(raw_path).expanduser().resolve(strict=False)
    if not path.exists() or not path.is_dir():
        raise ValueError("The local evidence root must be an existing directory.")
    if not os.access(path, os.W_OK):
        raise ValueError("The local evidence root must be writable.")

    settings = session.get(ProfessionalEvidenceSettings, _SETTINGS_ID)
    if settings is None:
        settings = ProfessionalEvidenceSettings(
            id=_SETTINGS_ID,
            root_path=str(path),
            verified_at=utc_now(),
        )
        session.add(settings)
    else:
        settings.root_path = str(path)
        settings.verified_at = utc_now()
    session.commit()
    return _response(settings)


def clear_professional_evidence_root(session: Session) -> ProfessionalEvidenceRootResponse:
    settings = session.get(ProfessionalEvidenceSettings, _SETTINGS_ID)
    if settings is not None:
        session.delete(settings)
        session.commit()
    return _response(None)


def resolve_professional_evidence_path(
    root_path: str, capture_run_id: str, source_id: str, filename: str
) -> Path:
    if any(not value or value in {".", ".."} for value in (capture_run_id, source_id, filename)):
        raise ValueError("Run, source, and filename must be non-empty safe path components.")
    if any(Path(value).name != value for value in (capture_run_id, source_id, filename)):
        raise ValueError("Run, source, and filename must be direct path components.")

    root = Path(root_path).resolve(strict=False)
    candidate = (root / capture_run_id / source_id / filename).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Evidence path must remain contained under the configured root.") from exc
    return candidate
