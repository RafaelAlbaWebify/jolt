from __future__ import annotations

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_runtime_identity_exposes_local_truth_without_mutating_evidence_root(tmp_path) -> None:
    database_path = tmp_path / "runtime-identity.db"
    client = TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))

    response = client.get("/api/runtime-identity")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "jolt-backend"
    assert payload["version"] == "0.8.0"
    assert payload["git"]["repository_root"]
    assert payload["git"]["commit_sha"]
    assert payload["database"]["database_path"] == database_path.as_posix()
    assert payload["database"]["alembic_revision"] == "20260730_0018"
    assert payload["database"]["record_counts"]["postings"] == 0
    assert payload["database"]["record_counts"]["applications"] == 0
    assert payload["database"]["record_counts"]["professional_capture_runs"] == 0
    assert payload["evidence_root"] == {
        "configured": False,
        "root_path": None,
        "exists": False,
        "writable": False,
        "verified_at": None,
    }
    assert payload["process"]["process_id"] > 0
    assert payload["process"]["python_executable"]
    assert payload["process"]["python_version"]
