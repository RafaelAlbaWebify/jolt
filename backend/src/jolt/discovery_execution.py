from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import time
import zipfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
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
    current_page: int
    pages_visited: int
    captured_count: int
    target_jobs: int
    max_pages: int
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
        current_page=execution.current_page,
        pages_visited=execution.pages_visited,
        captured_count=execution.captured_count,
        target_jobs=execution.target_jobs,
        max_pages=execution.max_pages,
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
            DiscoveryExecution.status.in_(
                ("queued", "starting_chrome", "waiting_results", "capturing")
            ),
        )
        .limit(1)
    )
    if active is not None:
        raise ValueError("Another Indeed discovery execution is already active.")

    definition = json.loads(search.definition_json)
    max_pages = max(1, min(10, int(definition.get("max_pages", 3) or 3)))

    now = utc_now()
    execution = DiscoveryExecution(
        id=str(uuid4()),
        source=search.source,
        saved_search_id=search.id,
        label_snapshot=search.label,
        status="queued",
        capture_run_id=None,
        current_page=0,
        pages_visited=0,
        captured_count=0,
        target_jobs=search.max_jobs,
        max_pages=max_pages,
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
                DiscoveryExecution.status.in_(
                    ("queued", "starting_chrome", "waiting_results", "capturing")
                )
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
            "Indeed execution did not persist a capture run." + (f" {error}" if error else "")
        )
    return capture_run_id


def run_indeed_saved_search(
    search: DiscoverySavedSearch,
    execution_id: str,
    *,
    api_url: str = "http://127.0.0.1:8000",
    phase_callback: Callable[[str, int | None, int | None], None] | None = None,
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
        "-SkipSync",
    ]
    if phase_callback is not None:
        phase_callback("starting_chrome", None, None)

    process = subprocess.Popen(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    output_lines: list[str] = []
    output_queue: Queue[str | None] = Queue()

    def read_output() -> None:
        assert process.stdout is not None
        try:
            for line in process.stdout:
                output_queue.put(line.rstrip())
        finally:
            output_queue.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()

    deadline = time.monotonic() + 3600
    stream_finished = False
    while True:
        if time.monotonic() >= deadline:
            process.kill()
            raise RuntimeError("Indeed supervised capture timed out after 3600 seconds.")

        try:
            text_line = output_queue.get(timeout=0.25)
            if text_line is None:
                stream_finished = True
            elif text_line:
                output_lines.append(text_line)
                if len(output_lines) > 200:
                    output_lines = output_lines[-200:]
                normalized = text_line.casefold()
                if phase_callback is not None:
                    progress = re.search(
                        r"^progress: page (\d+)/(\d+) · captured (\d+)/(\d+)$",
                        normalized,
                    )
                    if progress is not None:
                        phase_callback(
                            "capturing",
                            int(progress.group(1)),
                            int(progress.group(3)),
                        )
                    elif (
                        "chrome is ready" in normalized
                        or "waiting for visible indeed job results" in normalized
                    ):
                        phase_callback("waiting_results", None, None)
                    elif (
                        normalized.startswith("page ")
                        or "opening indeed results page" in normalized
                        or "jolt is attached to google chrome" in normalized
                    ):
                        phase_callback("capturing", None, None)
        except Empty:
            pass

        returncode = process.poll()
        if returncode is not None and stream_finished:
            break

    reader.join(timeout=2)
    if returncode != 0:
        diagnostic = "\n".join(output_lines[-80:])
        raise RuntimeError(
            f"Indeed supervised capture failed with exit code {returncode}."
            + (f" {diagnostic}" if diagnostic else "")
        )
    return _capture_run_id(output_zip)


def execute_discovery_execution(
    session: Session,
    execution_id: str,
    *,
    runner: Callable[..., str] | None = None,
) -> None:
    execution = session.get(DiscoveryExecution, execution_id)
    if execution is None:
        raise JoltNotFoundError("Discovery execution was not found.")
    if execution.status != "queued":
        raise ValueError("Only queued discovery executions can be started.")

    search = session.get(DiscoverySavedSearch, execution.saved_search_id)
    if search is None or search.source != execution.source:
        raise JoltNotFoundError("Saved discovery search was not found.")

    execution.status = "starting_chrome"
    execution.started_at = utc_now()
    execution.error = ""
    session.commit()

    def set_phase(
        phase: str,
        current_page: int | None = None,
        captured_count: int | None = None,
    ) -> None:
        current = session.get(DiscoveryExecution, execution_id)
        if current is None:
            return
        current.status = phase
        if current_page is not None:
            current.current_page = current_page
            current.pages_visited = max(current.pages_visited, current_page)
        if captured_count is not None:
            current.captured_count = captured_count
        session.commit()

    selected_runner = runner or run_indeed_saved_search
    try:
        if runner is None:
            capture_run_id = selected_runner(
                search,
                execution.id,
                phase_callback=set_phase,
            )
        else:
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
