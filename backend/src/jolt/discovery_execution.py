from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from datetime import datetime
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import DiscoveryExecution, DiscoverySavedSearch, utc_now
from jolt.errors import JoltNotFoundError


class DiscoveryExecutionCreateRequest(BaseModel):
    source: str
    saved_search_id: str


class DiscoveryExecutionResponse(BaseModel):
    id: str
    source: str
    saved_search_id: str
    label: str
    status: str
    capture_run_id: str | None
    error: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _response(execution: DiscoveryExecution) -> DiscoveryExecutionResponse:
    return DiscoveryExecutionResponse(
        id=execution.id,
        source=execution.source,
        saved_search_id=execution.saved_search_id,
        label=execution.label_snapshot,
        status=execution.status,
        capture_run_id=execution.capture_run_id,
        error=execution.error,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        created_at=execution.created_at,
    )


def list_discovery_executions(session: Session) -> list[DiscoveryExecutionResponse]:
    rows = session.scalars(
        select(DiscoveryExecution).order_by(
            DiscoveryExecution.created_at.desc(),
            DiscoveryExecution.id.desc(),
        )
    ).all()
    return [_response(row) for row in rows]


def get_discovery_execution(
    session: Session,
    execution_id: str,
) -> DiscoveryExecutionResponse:
    execution = session.get(DiscoveryExecution, execution_id)
    if execution is None:
        raise JoltNotFoundError("Discovery execution was not found.")
    return _response(execution)


def create_discovery_execution(
    session: Session,
    request: DiscoveryExecutionCreateRequest,
) -> DiscoveryExecutionResponse:
    if request.source != "indeed":
        raise ValueError("This execution endpoint currently supports Indeed saved searches only.")

    search = session.get(DiscoverySavedSearch, request.saved_search_id)
    if search is None or search.source != request.source:
        raise JoltNotFoundError("Saved discovery search was not found.")
    if not search.enabled:
        raise ValueError("Disabled discovery searches cannot be executed.")

    active = session.scalar(
        select(DiscoveryExecution.id)
        .where(
            DiscoveryExecution.source == "indeed",
            DiscoveryExecution.status.in_(("queued", "running")),
        )
        .limit(1)
    )
    if active is not None:
        raise ValueError("Another Indeed discovery execution is already active.")

    now = utc_now()
    execution = DiscoveryExecution(
        id=str(uuid4()),
        source=search.source,
        saved_search_id=search.id,
        label_snapshot=search.label,
        status="queued",
        capture_run_id=None,
        error="",
        started_at=None,
        completed_at=None,
        created_at=now,
    )
    session.add(execution)
    session.commit()
    return _response(execution)


def recover_interrupted_discovery_executions(session: Session) -> int:
    rows = list(
        session.scalars(
            select(DiscoveryExecution).where(
                DiscoveryExecution.status.in_(("queued", "running"))
            )
        ).all()
    )
    if not rows:
        return 0
    now = utc_now()
    for row in rows:
        row.status = "failed"
        row.error = (
            "Discovery execution was interrupted because the JOLT backend stopped or restarted."
        )
        row.completed_at = now
    session.commit()
    return len(rows)


def _capture_run_id(output_zip: Path) -> str:
    if not output_zip.exists():
        raise RuntimeError("Indeed execution finished without creating its evidence package.")
    with zipfile.ZipFile(output_zip) as archive:
        result = json.loads(archive.read("api_result.json"))
    capture_run_id = str(result.get("capture_run_id", "") or "")
    if not capture_run_id:
        error = str(result.get("error", "") or result.get("response", "") or "")
        raise RuntimeError(
            "Indeed execution did not persist a capture run."
            + (f" {error}" if error else "")
        )
    return capture_run_id


def run_indeed_saved_search(
    search: DiscoverySavedSearch,
    execution_id: str,
    *,
    api_url: str = "http://127.0.0.1:8000",
) -> str:
    definition = json.loads(search.definition_json)
    search_url = str(definition.get("search_url", "") or "").strip()
    if not search_url:
        raise ValueError("Indeed saved search is missing search_url.")
    max_pages = int(definition.get("max_pages", 3) or 3)
    max_pages = max(1, min(10, max_pages))

    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        raise RuntimeError("PowerShell is required to run supervised Indeed discovery.")

    root = _repo_root()
    evidence_dir = root / ".jolt" / "discovery-executions" / execution_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    output_zip = evidence_dir / "indeed_capture.zip"
    script = root / "tools" / "run-indeed-chrome-capture.ps1"

    command = [
        shell,
        "-NoProfile",
        "-File",
        str(script),
        "-SearchUrl",
        search_url,
        "-MaxJobs",
        str(search.max_jobs),
        "-MaxPages",
        str(max_pages),
        "-ApiUrl",
        api_url,
        "-OutputZip",
        str(output_zip),
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=3600,
        check=False,
    )
    if completed.returncode != 0:
        diagnostic = "\n".join(
            part.strip()
            for part in (completed.stdout[-3000:], completed.stderr[-3000:])
            if part.strip()
        )
        raise RuntimeError(
            f"Indeed supervised capture failed with exit code {completed.returncode}."
            + (f" {diagnostic}" if diagnostic else "")
        )
    return _capture_run_id(output_zip)


def execute_discovery_execution(
    session: Session,
    execution_id: str,
    *,
    runner: Callable[[DiscoverySavedSearch, str], str] | None = None,
) -> None:
    execution = session.get(DiscoveryExecution, execution_id)
    if execution is None:
        raise JoltNotFoundError("Discovery execution was not found.")
    if execution.status != "queued":
        raise ValueError("Only queued discovery executions can be started.")

    search = session.get(DiscoverySavedSearch, execution.saved_search_id)
    if search is None or search.source != execution.source:
        raise JoltNotFoundError("Saved discovery search was not found.")

    execution.status = "running"
    execution.started_at = utc_now()
    execution.error = ""
    session.commit()

    selected_runner = runner or run_indeed_saved_search
    try:
        capture_run_id = selected_runner(search, execution.id)
        execution.capture_run_id = capture_run_id
        execution.status = "completed"
        execution.completed_at = utc_now()
        session.commit()
    except Exception as exc:
        session.rollback()
        execution = session.get(DiscoveryExecution, execution_id)
        if execution is not None:
            execution.status = "failed"
            execution.error = str(exc)
            execution.completed_at = utc_now()
            session.commit()
        raise
