from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import ModuleType

from playwright.sync_api import Page

OUTCOMES_PATH = Path(__file__).with_name(
    "jolt-full-cycle-playwright-certification-outcomes.py"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_URL = "http://127.0.0.1:8000/api/health"
FRONTEND_URL = "http://127.0.0.1:5173"


def load_outcomes() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "jolt_full_cycle_outcomes_with_restart", OUTCOMES_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load outcome certification from {OUTCOMES_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def required_path(name: str) -> Path:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not configured.")
    return Path(value).resolve()


def endpoint_available(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError):
        return False


def wait_for_endpoint(url: str, *, available: bool, timeout: float = 45) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if endpoint_available(url) is available:
            return
        time.sleep(0.25)
    state = "available" if available else "unavailable"
    raise TimeoutError(f"Timed out waiting for {url} to become {state}.")


def read_process_group(pid_file: Path) -> int:
    try:
        return int(pid_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Invalid service PID file: {pid_file}") from exc


def stop_process_group(pid_file: Path) -> None:
    process_group = read_process_group(pid_file)
    try:
        os.killpg(process_group, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            os.killpg(process_group, 0)
        except ProcessLookupError:
            return
        time.sleep(0.2)
    os.killpg(process_group, signal.SIGKILL)


def start_service(
    command: list[str],
    *,
    cwd: Path,
    log_path: Path,
    pid_file: Path,
) -> subprocess.Popen[bytes]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("ab", buffering=0)
    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=cwd,
        env=os.environ.copy(),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    pid_file.write_text(str(process.pid), encoding="utf-8")
    return process


def application_snapshot(application_id: str) -> dict[str, object]:
    request = urllib.request.Request(
        f"http://127.0.0.1:8000/api/applications/{application_id}",
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def restart_and_verify(
    module: ModuleType,
    page: Page,
    fixture: dict[str, str],
    actions: list[dict[str, str]],
) -> None:
    backend_pid_file = required_path("JOLT_CERT_BACKEND_PID_FILE")
    frontend_pid_file = required_path("JOLT_CERT_FRONTEND_PID_FILE")
    backend_log = required_path("JOLT_CERT_BACKEND_LOG")
    frontend_log = required_path("JOLT_CERT_FRONTEND_LOG")

    before = application_snapshot(fixture["application_id"])
    before_events = len(before.get("events", []))
    if before_events < 1:
        raise AssertionError("Application has no persisted events before service restart.")

    page.goto("about:blank", wait_until="load")
    stop_process_group(frontend_pid_file)
    stop_process_group(backend_pid_file)
    wait_for_endpoint(FRONTEND_URL, available=False)
    wait_for_endpoint(BACKEND_URL, available=False)
    module.record_action(actions, "Stop disposable frontend and backend", "passed")

    backend = start_service(
        [
            "uv",
            "run",
            "uvicorn",
            "jolt.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=REPOSITORY_ROOT / "backend",
        log_path=backend_log,
        pid_file=backend_pid_file,
    )
    frontend = start_service(
        ["npm", "run", "dev", "--", "--host", "127.0.0.1"],
        cwd=REPOSITORY_ROOT / "frontend",
        log_path=frontend_log,
        pid_file=frontend_pid_file,
    )
    try:
        wait_for_endpoint(BACKEND_URL, available=True)
        wait_for_endpoint(FRONTEND_URL, available=True)
    except Exception:
        backend.poll()
        frontend.poll()
        raise
    module.record_action(actions, "Restart disposable frontend and backend", "passed")

    after = application_snapshot(fixture["application_id"])
    if after.get("application_id") != fixture["application_id"]:
        raise AssertionError("Application identity changed across service restart.")
    if len(after.get("events", [])) != before_events:
        raise AssertionError(
            "Application event count changed across service restart: "
            f"{before_events} -> {len(after.get('events', []))}"
        )

    page.goto(FRONTEND_URL, wait_until="networkidle")
    module.open_application(page, fixture)
    dialog = page.get_by_role("dialog", name=fixture["title"])
    dialog.get_by_role("tab", name="Tasks", exact=True).click()
    dialog.get_by_text("corrected", exact=False).first.wait_for(timeout=30_000)
    dialog.get_by_role("tab", name="Timeline", exact=True).click()
    dialog.get_by_role("heading", name="Timeline", exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Persisted application survives service restart", "passed")
    page.screenshot(
        path=Path(
            "../artifacts/full-cycle-certification/evidence/screenshots/009-service-restart-persistence.png"
        ),
        full_page=True,
    )


def main() -> int:
    outcomes = load_outcomes()
    original_outcome_cycle = outcomes.exercise_outcome_cycle

    def restart_then_outcome(
        module: ModuleType,
        page: Page,
        fixture: dict[str, str],
        actions: list[dict[str, str]],
    ) -> None:
        restart_and_verify(module, page, fixture, actions)
        original_outcome_cycle(module, page, fixture, actions)

    outcomes.exercise_outcome_cycle = restart_then_outcome
    return int(outcomes.main())


if __name__ == "__main__":
    raise SystemExit(main())