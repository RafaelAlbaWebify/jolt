from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from jolt.database import create_session_factory
from jolt.main import create_app
from jolt.professional_intelligence_capture_runs import AUTHORIZATION_CONFIRMATION_PHRASE
from jolt.professional_intelligence_supervised_capture import start_professional_supervised_capture


def _client_and_factory(tmp_path: Path):
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    return TestClient(create_app(database_url)), create_session_factory(database_url)


def test_failed_source_capture_records_diagnostic_artifact_and_progress_detail(
    tmp_path: Path,
) -> None:
    client, factory = _client_and_factory(tmp_path)
    evidence_root = tmp_path / "evidence"
    configured = client.post(
        "/api/professional-intelligence/evidence-root",
        json={"root_path": str(evidence_root)},
    )
    assert configured.status_code == 200

    created = client.post(
        "/api/professional-intelligence/capture-runs",
        json={
            "options": {
                "max_sources": 1,
                "max_scroll_batches": 1,
                "max_items_per_source": 5,
                "timeout_seconds": 10,
                "stop_on_failure": True,
            }
        },
    )
    assert created.status_code == 200
    run = created.json()
    run_id = run["id"]
    source = run["planned_sources"][0]

    authorized = client.post(
        f"/api/professional-intelligence/capture-runs/{run_id}/authorize",
        json={
            "confirmation_phrase": AUTHORIZATION_CONFIRMATION_PHRASE,
            "user_present": True,
        },
    )
    assert authorized.status_code == 200

    def failing_capture_source(url: str):
        raise RuntimeError(f"synthetic browser failure for {url}")

    with factory() as session:
        response = start_professional_supervised_capture(
            session,
            run_id,
            capture_source=failing_capture_source,
        )

    assert response.status == "completed_with_gaps"
    assert response.artifact_count == 1
    assert response.source_progress[0].status == "failed"
    assert response.source_progress[0].completeness_status == "failed"
    assert source["url"] in response.source_progress[0].detail
    assert response.stop_reason == "stopped_after_first_source_failure"

    diagnostic_path = (
        evidence_root
        / "professional-intelligence"
        / run_id
        / source["source_id"]
        / "page-diagnostics.json"
    )
    assert diagnostic_path.exists()
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert diagnostic["source_id"] == source["source_id"]
    assert diagnostic["requested_url"] == source["url"]
    assert diagnostic["source_label"] == source["label"]
    assert diagnostic["error_stage"] == "capture_or_artifact_write"
    assert diagnostic["screenshot_attempted"] is False
    assert any("synthetic browser failure" in error for error in diagnostic["errors"])
