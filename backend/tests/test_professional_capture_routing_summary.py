from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))


def test_professional_capture_routing_summary_classifies_sources(tmp_path: Path) -> None:
    client = _client(tmp_path)

    created = client.post(
        "/api/professional-intelligence/capture-runs",
        json={
            "options": {
                "max_sources": 8,
                "max_scroll_batches": 1,
                "max_items_per_source": 5,
                "timeout_seconds": 10,
                "stop_on_failure": True,
            }
        },
    )
    assert created.status_code == 200
    run = created.json()

    summary = client.get(
        f"/api/professional-intelligence/capture-runs/{run['id']}/routing-summary"
    )
    assert summary.status_code == 200
    payload = summary.json()

    assert payload["capture_run_id"] == run["id"]
    assert payload["run_status"] == "planned"
    assert payload["artifact_count"] == 0
    assert payload["total_sources"] == len(run["planned_sources"])
    assert payload["completed_sources"] == 0
    assert payload["counts"]["job_opportunities"] == 0
    assert payload["counts"]["linkedin_presence"] >= 1
    assert payload["counts"]["market_signals"] >= 1
    assert payload["counts"]["rejected_noise"] == 0
    assert payload["decisions"]
    assert {item["target_bucket"] for item in payload["decisions"]} >= {
        "linkedin_presence",
        "market_signal",
    }
    assert all(item["routing_status"] == "pending" for item in payload["decisions"])
    assert "Verified job-item capture uses the canonical opportunity pipeline" in payload["explanation"]


def test_professional_capture_routing_summary_404s_for_missing_run(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get(
        "/api/professional-intelligence/capture-runs/missing/routing-summary"
    )

    assert response.status_code == 404
