from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_capture_run_deletion_requires_confirmation_and_removes_only_selected_run(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    first = client.post("/api/professional-intelligence/capture-runs").json()
    second = client.post("/api/professional-intelligence/capture-runs").json()
    evidence_root = Path(client.get("/api/professional-intelligence/evidence-root").json()["root_path"])
    first_directory = evidence_root / first["id"] / "linkedin-profile"
    first_directory.mkdir(parents=True)
    (first_directory / "page.html").write_text("fixture", encoding="utf-8")

    rejected = client.post(
        f"/api/professional-intelligence/capture-runs/{first['id']}/delete",
        json={"confirmation_phrase": "delete"},
    )
    assert rejected.status_code == 409
    assert first_directory.exists()

    deleted = client.post(
        f"/api/professional-intelligence/capture-runs/{first['id']}/delete",
        json={"confirmation_phrase": "DELETE CAPTURE RUN"},
    )
    assert deleted.status_code == 200
    assert deleted.json() == {
        "run_id": first["id"],
        "deleted_artifact_count": 0,
        "deleted_evidence_directory": True,
    }
    assert not (evidence_root / first["id"]).exists()

    runs = client.get("/api/professional-intelligence/capture-runs").json()
    assert [run["id"] for run in runs] == [second["id"]]


def test_running_capture_run_cannot_be_deleted(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))
    created = client.post("/api/professional-intelligence/capture-runs").json()

    # The domain contract refuses running deletion even when exact confirmation is supplied.
    from jolt.database import create_session_factory
    from jolt.professional_intelligence_records import ProfessionalCaptureRun

    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    try:
        run = session.get(ProfessionalCaptureRun, created["id"])
        assert run is not None
        run.status = "running"
        session.commit()
    finally:
        session.close()

    response = client.post(
        f"/api/professional-intelligence/capture-runs/{created['id']}/delete",
        json={"confirmation_phrase": "DELETE CAPTURE RUN"},
    )
    assert response.status_code == 409
    assert "cancelled" in response.json()["detail"]
