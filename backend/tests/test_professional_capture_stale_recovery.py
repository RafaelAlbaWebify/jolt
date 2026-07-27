from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(database: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{database.as_posix()}"))


def _set_running(database: Path, run_id: str, started_at: datetime | None) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE professional_capture_runs
            SET status = 'running', started_at = ?, completed_at = NULL, stop_reason = ''
            WHERE id = ?
            """,
            (started_at.isoformat() if started_at else None, run_id),
        )
        connection.commit()


def test_stale_running_capture_is_recovered_on_detail_after_restart(tmp_path: Path) -> None:
    database = tmp_path / "stale-detail.db"
    client = _client(database)
    run = client.post("/api/professional-intelligence/capture-runs").json()
    _set_running(database, run["id"], datetime.now(UTC) - timedelta(minutes=31))

    restarted = _client(database)
    recovered = restarted.get(
        f"/api/professional-intelligence/capture-runs/{run['id']}"
    )

    assert recovered.status_code == 200
    payload = recovered.json()
    assert payload["status"] == "interrupted"
    assert payload["stop_reason"] == "stale_running_run_recovered"
    assert payload["completed_at"] is not None

    second_restart = _client(database)
    persisted = second_restart.get(
        f"/api/professional-intelligence/capture-runs/{run['id']}"
    ).json()
    assert persisted["status"] == "interrupted"
    assert persisted["completed_at"] == payload["completed_at"]


def test_running_capture_without_start_timestamp_is_recovered_on_ledger_load(
    tmp_path: Path,
) -> None:
    database = tmp_path / "missing-start.db"
    client = _client(database)
    run = client.post("/api/professional-intelligence/capture-runs").json()
    _set_running(database, run["id"], None)

    history = _client(database).get("/api/professional-intelligence/capture-runs")

    assert history.status_code == 200
    recovered = next(item for item in history.json() if item["id"] == run["id"])
    assert recovered["status"] == "interrupted"
    assert recovered["stop_reason"] == "stale_running_run_recovered"


def test_recent_running_capture_is_not_reclassified(tmp_path: Path) -> None:
    database = tmp_path / "recent.db"
    client = _client(database)
    run = client.post("/api/professional-intelligence/capture-runs").json()
    _set_running(database, run["id"], datetime.now(UTC) - timedelta(minutes=5))

    detail = _client(database).get(
        f"/api/professional-intelligence/capture-runs/{run['id']}"
    )

    assert detail.status_code == 200
    assert detail.json()["status"] == "running"
    assert detail.json()["completed_at"] is None
    assert detail.json()["stop_reason"] == ""
