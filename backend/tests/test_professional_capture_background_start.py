from pathlib import Path

from fastapi.testclient import TestClient

from jolt.database import create_session_factory, utc_now
from jolt.main import create_app
from jolt.professional_intelligence_records import ProfessionalCaptureRun

AUTHORIZATION_PHRASE = "I UNDERSTAND THIS WILL OPEN LINKEDIN"


def test_professional_capture_start_returns_running_and_queues_background_task(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))
    created = client.post("/api/professional-intelligence/capture-runs").json()
    authorized = client.post(
        f"/api/professional-intelligence/capture-runs/{created['id']}/authorize",
        json={"confirmation_phrase": AUTHORIZATION_PHRASE, "user_present": True},
    )
    assert authorized.status_code == 200

    calls: list[str] = []

    def fake_start_bounded_professional_capture(session, run_id: str):  # type: ignore[no-untyped-def]
        calls.append(run_id)
        run = session.get(ProfessionalCaptureRun, run_id)
        assert run is not None
        run.mode = "supervised_read_only"
        run.status = "completed"
        run.started_at = run.started_at or utc_now()
        run.completed_at = utc_now()
        run.stop_reason = ""
        session.commit()

    monkeypatch.setattr(
        "jolt.professional_intelligence_plan_api.start_bounded_professional_capture",
        fake_start_bounded_professional_capture,
    )

    started = client.post(f"/api/professional-intelligence/capture-runs/{created['id']}/start")

    assert started.status_code == 200
    assert started.json()["status"] == "running"
    assert started.json()["stop_reason"] == "capture_queued"
    assert calls == [created["id"]]

    reloaded = client.get(f"/api/professional-intelligence/capture-runs/{created['id']}").json()
    assert reloaded["status"] == "completed"


def test_professional_capture_background_failure_marks_run_failed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))
    created = client.post("/api/professional-intelligence/capture-runs").json()
    client.post(
        f"/api/professional-intelligence/capture-runs/{created['id']}/authorize",
        json={"confirmation_phrase": AUTHORIZATION_PHRASE, "user_present": True},
    )

    def fake_start_bounded_professional_capture(session, run_id: str):  # type: ignore[no-untyped-def]
        raise RuntimeError("Playwright browser failed before capture started")

    monkeypatch.setattr(
        "jolt.professional_intelligence_plan_api.start_bounded_professional_capture",
        fake_start_bounded_professional_capture,
    )

    started = client.post(f"/api/professional-intelligence/capture-runs/{created['id']}/start")

    assert started.status_code == 200
    assert started.json()["status"] == "running"

    session = create_session_factory(database_url)()
    try:
        run = session.get(ProfessionalCaptureRun, created["id"])
        assert run is not None
        assert run.status == "failed"
        assert run.stop_reason == "capture_background_failure"
        assert run.completed_at is not None
    finally:
        session.close()
