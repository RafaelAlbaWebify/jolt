from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))


def test_execution_readiness_remains_blocked_without_browser_runner(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/professional-intelligence/execution-readiness")

    assert response.status_code == 200
    readiness = response.json()
    assert readiness["ready"] is False
    assert readiness["execution_available"] is False
    assert "supervised_browser_runner_not_implemented" in readiness["blockers"]
    assert "explicit_per_run_user_confirmation_not_implemented" in readiness["blockers"]
    assert "visible_rendered_dom_text_is_primary" in readiness["evidence_policy"]["text_extraction_policy"]
    assert "browser_storage_state" in readiness["evidence_policy"]["prohibited_evidence"]


def test_artifact_manifest_accepts_safe_run_scoped_entry(tmp_path: Path) -> None:
    client = _client(tmp_path)
    run = client.post("/api/professional-intelligence/capture-runs").json()
    source_id = run["planned_sources"][0]["source_id"]

    response = client.post(
        "/api/professional-intelligence/artifact-manifest/validate",
        json={
            "capture_run_id": run["id"],
            "source_id": source_id,
            "artifact_type": "screenshot_png",
            "relative_path": f"professional-intelligence/{run['id']}/{source_id}/page.png",
            "sha256": "A" * 64,
            "completeness_status": "complete",
            "retention_days": 30,
        },
    )

    assert response.status_code == 200
    assert response.json()["sha256"] == "a" * 64


def test_artifact_manifest_rejects_path_traversal_unknown_source_and_bad_hash(tmp_path: Path) -> None:
    client = _client(tmp_path)
    run = client.post("/api/professional-intelligence/capture-runs").json()
    source_id = run["planned_sources"][0]["source_id"]
    base = {
        "capture_run_id": run["id"],
        "source_id": source_id,
        "artifact_type": "rendered_text_json",
        "relative_path": f"professional-intelligence/{run['id']}/{source_id}/text.json",
        "sha256": "b" * 64,
        "completeness_status": "partial",
        "retention_days": 30,
    }

    traversal = client.post(
        "/api/professional-intelligence/artifact-manifest/validate",
        json={**base, "relative_path": "../outside.json"},
    )
    assert traversal.status_code == 422

    unknown_source = client.post(
        "/api/professional-intelligence/artifact-manifest/validate",
        json={**base, "source_id": "linkedin-feed"},
    )
    assert unknown_source.status_code == 422

    bad_hash = client.post(
        "/api/professional-intelligence/artifact-manifest/validate",
        json={**base, "sha256": "not-a-hash"},
    )
    assert bad_hash.status_code == 422


def test_artifact_manifest_rejects_retention_and_extension_mismatch(tmp_path: Path) -> None:
    client = _client(tmp_path)
    run = client.post("/api/professional-intelligence/capture-runs").json()
    source_id = run["planned_sources"][0]["source_id"]
    base = {
        "capture_run_id": run["id"],
        "source_id": source_id,
        "artifact_type": "screenshot_png",
        "relative_path": f"professional-intelligence/{run['id']}/{source_id}/page.png",
        "sha256": "c" * 64,
        "completeness_status": "failed",
        "retention_days": 30,
    }

    bad_extension = client.post(
        "/api/professional-intelligence/artifact-manifest/validate",
        json={**base, "relative_path": f"professional-intelligence/{run['id']}/{source_id}/page.json"},
    )
    assert bad_extension.status_code == 422

    excessive_retention = client.post(
        "/api/professional-intelligence/artifact-manifest/validate",
        json={**base, "retention_days": 366},
    )
    assert excessive_retention.status_code == 422
