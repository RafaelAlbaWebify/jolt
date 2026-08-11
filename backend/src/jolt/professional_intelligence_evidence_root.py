from __future__ import annotations

import os
import time
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from jolt.database import utc_now
from jolt.professional_intelligence_records import ProfessionalEvidenceSettings

_SETTINGS_ID = "professional-evidence"
_DEFAULT_DIRECTORY_NAME = "professional-evidence"
_PROVISION_ATTEMPTS = 5


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


def _default_evidence_root(session: Session) -> Path:
    bind = session.get_bind()
    database_path = bind.url.database if isinstance(bind, Engine) else bind.engine.url.database
    if database_path and database_path != ":memory:":
        return (
            Path(database_path).expanduser().resolve(strict=False).parent / _DEFAULT_DIRECTORY_NAME
        )
    return Path(__file__).resolve().parents[2] / "data" / _DEFAULT_DIRECTORY_NAME


def _wait_for_committed_professional_evidence_root(
    session: Session,
) -> ProfessionalEvidenceSettings | None:
    """Wait briefly for a concurrent singleton insert to become visible."""

    for attempt in range(_PROVISION_ATTEMPTS):
        session.expire_all()
        existing = session.get(ProfessionalEvidenceSettings, _SETTINGS_ID)
        if existing is not None:
            return existing
        if attempt < _PROVISION_ATTEMPTS - 1:
            time.sleep(0.05 * (attempt + 1))
    return None


def ensure_default_professional_evidence_root(session: Session) -> ProfessionalEvidenceSettings:
    settings = session.get(ProfessionalEvidenceSettings, _SETTINGS_ID)
    if settings is not None:
        return settings

    path = _default_evidence_root(session)
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir() or not os.access(path, os.W_OK):
        raise ValueError("JOLT could not provision a writable local evidence directory.")

    last_conflict: IntegrityError | OperationalError | None = None
    for _attempt in range(_PROVISION_ATTEMPTS):
        settings = ProfessionalEvidenceSettings(
            id=_SETTINGS_ID,
            root_path=str(path),
            verified_at=utc_now(),
        )
        session.add(settings)
        try:
            session.commit()
            return settings
        except (IntegrityError, OperationalError) as exc:
            # Evidence root and execution-readiness are loaded concurrently by the UI.
            # A competing request can win the singleton insert while its commit is not
            # yet visible to this session. Roll back and wait for that committed winner
            # before attempting another insert.
            session.rollback()
            last_conflict = exc
            existing = _wait_for_committed_professional_evidence_root(session)
            if existing is not None:
                return existing
    if last_conflict is not None:
        raise last_conflict
    raise ValueError("JOLT could not provision the local evidence directory.")


def get_professional_evidence_root(session: Session) -> ProfessionalEvidenceRootResponse:
    return _response(ensure_default_professional_evidence_root(session))


def configure_professional_evidence_root(
    session: Session, request: ProfessionalEvidenceRootRequest
) -> ProfessionalEvidenceRootResponse:
    raw_path = request.root_path.strip()
    if not raw_path:
        raise ValueError("A local evidence directory is required.")
    path = Path(raw_path).expanduser().resolve(strict=False)
    if path.exists() and not path.is_dir():
        raise ValueError("The local evidence root must be a directory.")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError("The local evidence root could not be created.") from exc
    if not path.is_dir():
        raise ValueError("The local evidence root must be a directory.")
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
    return _response(ensure_default_professional_evidence_root(session))


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
