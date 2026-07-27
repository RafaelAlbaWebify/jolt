import json
from pathlib import Path

from fastapi.testclient import TestClient

from jolt.database import create_session_factory
from jolt.main import create_app
from jolt.professional_intelligence_capture_runs import AUTHORIZATION_CONFIRMATION_PHRASE
from jolt.professional_intelligence_records import ProfessionalCaptureRun
from jolt.professional_intelligence_supervised_capture import (
    CapturedProfessionalPage,
    start_professional_supervised_capture,
)


def _authorized_run(tmp_path: Path) -> tuple[str, str]:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    client = TestClient(create_app(database_url))
    configured = client.post(
        "/api/professional-intelligence/evidence-root",
        json={"root_path": str(evidence_root)},
    )
    assert configured.status_code == 200
    planned = client.post("/api/professional-intelligence/capture-runs").json()
    assert planned["total_source_count"] == 8
    assert planned["completed_source_count"] == 0
    assert {item["status"] for item in planned["source_progress"]} == {"pending"}
    authorized = client.post(
        f"/api/professional-intelligence/capture-runs/{planned['id']}/authorize",
        json={
            "confirmation_phrase": AUTHORIZATION_CONFIRMATION_PHRASE,
            "user_present": True,
        },
    )
    assert authorized.status_code == 200
    return database_url, planned["id"]


def test_running_capture_persists_progress_and_honors_cancellation(tmp_path: Path) -> None:
    database_url, run_id = _authorized_run(tmp_path)
    factory = create_session_factory(database_url)
    calls = 0

    def capture_source(url: str) -> CapturedProfessionalPage:
        nonlocal calls
        calls += 1
        if calls == 1:
            with factory() as cancellation_session:
                running = cancellation_session.get(ProfessionalCaptureRun, run_id)
                assert running is not None
                assert running.status == "running"
                assert running.current_source_id
                running.cancel_requested = True
                cancellation_session.commit()
        return CapturedProfessionalPage(
            screenshot_png=b"fixture-png",
            visible_text=(f"Ready rendered evidence from {url}. " * 8),
            title="Ready fixture",
            final_url=url,
            http_status=200,
            readiness_status="network_idle_and_body_ready",
            readiness_detail="Fixture met both readiness conditions.",
        )

    with factory() as session:
        result = start_professional_supervised_capture(
            session,
            run_id,
            capture_source=capture_source,
        )

    assert calls == 1
    assert result.status == "cancelled"
    assert result.stop_reason == "cancelled_by_user"
    assert result.cancel_requested is True
    assert result.completed_source_count == 1
    assert result.current_source_id == ""
    assert result.completed_at is not None
    assert result.progress_updated_at is not None
    assert result.artifact_count == 4
    assert [item.status for item in result.source_progress].count("completed") == 1
    assert [item.status for item in result.source_progress].count("skipped") == 7
    assert result.source_progress[0].completeness_status == "complete"

    with factory() as session:
        persisted = session.get(ProfessionalCaptureRun, run_id)
        assert persisted is not None
        raw_progress = json.loads(persisted.source_progress_json)
        assert len(raw_progress) == 8
        assert raw_progress[0]["status"] == "completed"
        assert all(item["status"] == "skipped" for item in raw_progress[1:])
