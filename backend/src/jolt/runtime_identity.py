from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from jolt.professional_intelligence_records import ProfessionalEvidenceSettings


RECORD_COUNT_TABLES = (
    "source_documents",
    "postings",
    "evaluations",
    "review_decisions",
    "applications",
    "application_events",
    "outcomes",
    "application_tasks",
    "application_interviews",
    "application_contacts",
    "application_documents",
    "capture_runs",
    "capture_items",
    "professional_capture_runs",
    "professional_capture_artifacts",
)


class RuntimeGitIdentity(BaseModel):
    repository_root: str
    branch: str
    commit_sha: str
    dirty: bool | None
    source: str


class RuntimeDatabaseIdentity(BaseModel):
    database_url: str
    database_path: str | None
    alembic_revision: str
    record_counts: dict[str, int | None]


class RuntimeEvidenceRootIdentity(BaseModel):
    configured: bool
    root_path: str | None
    exists: bool
    writable: bool
    verified_at: str | None


class RuntimeProcessIdentity(BaseModel):
    process_id: int
    current_working_directory: str
    python_executable: str
    python_version: str
    platform: str


class RuntimeIdentityResponse(BaseModel):
    service: str
    version: str
    git: RuntimeGitIdentity
    database: RuntimeDatabaseIdentity
    evidence_root: RuntimeEvidenceRootIdentity
    process: RuntimeProcessIdentity


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _run_git(args: list[str], repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return completed.stdout.strip()


def _git_identity() -> RuntimeGitIdentity:
    repo_root = _repo_root()
    env_sha = os.getenv("GITHUB_SHA") or os.getenv("JOLT_GIT_SHA")
    try:
        branch = _run_git(["branch", "--show-current"], repo_root) or "detached"
        commit_sha = _run_git(["rev-parse", "HEAD"], repo_root)
        dirty = bool(_run_git(["status", "--porcelain"], repo_root))
        source = "git"
    except Exception:
        branch = os.getenv("GITHUB_REF_NAME") or os.getenv("JOLT_GIT_BRANCH") or "unknown"
        commit_sha = env_sha or "unknown"
        dirty = None
        source = "environment" if env_sha else "unavailable"

    return RuntimeGitIdentity(
        repository_root=str(repo_root),
        branch=branch,
        commit_sha=commit_sha,
        dirty=dirty,
        source=source,
    )


def _database_url(session: Session) -> tuple[str, str | None]:
    bind = session.get_bind()
    engine = bind if isinstance(bind, Engine) else bind.engine
    url = engine.url
    database_path = url.database if url.drivername.startswith("sqlite") else None
    return url.render_as_string(hide_password=False), database_path


def _alembic_revision(session: Session) -> str:
    try:
        revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    except Exception:
        return "unavailable"
    return str(revision or "")


def _record_counts(session: Session) -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    for table in RECORD_COUNT_TABLES:
        try:
            counts[table] = int(session.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one())
        except Exception:
            counts[table] = None
    return counts


def _evidence_root(session: Session) -> RuntimeEvidenceRootIdentity:
    settings = session.get(ProfessionalEvidenceSettings, "professional-evidence")
    if settings is None:
        return RuntimeEvidenceRootIdentity(
            configured=False,
            root_path=None,
            exists=False,
            writable=False,
            verified_at=None,
        )

    path = Path(settings.root_path)
    exists = path.is_dir()
    return RuntimeEvidenceRootIdentity(
        configured=True,
        root_path=str(path),
        exists=exists,
        writable=exists and os.access(path, os.W_OK),
        verified_at=settings.verified_at.isoformat(),
    )


def build_runtime_identity(session: Session) -> RuntimeIdentityResponse:
    database_url, database_path = _database_url(session)
    return RuntimeIdentityResponse(
        service="jolt-backend",
        version="0.8.0",
        git=_git_identity(),
        database=RuntimeDatabaseIdentity(
            database_url=database_url,
            database_path=database_path,
            alembic_revision=_alembic_revision(session),
            record_counts=_record_counts(session),
        ),
        evidence_root=_evidence_root(session),
        process=RuntimeProcessIdentity(
            process_id=os.getpid(),
            current_working_directory=str(Path.cwd()),
            python_executable=sys.executable,
            python_version=sys.version.split()[0],
            platform=platform.platform(),
        ),
    )
