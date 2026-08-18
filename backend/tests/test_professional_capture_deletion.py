from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_capture_run_deletion_requires_confirmation_and_removes_only_selected_governed_evidence(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    first = client.post("/api/professional-intelligence/capture-runs").json()
    second = client.post("/api/professional-intelligence/capture-runs").json()
    evidence_root = Path(
        client.get("/api/professional-intelligence/evidence-root").json()["root_path"]
    )
    governed_directory = (
        evidence_root / "professional-intelligence" / first["id"] / "linkedin-profile"
    )
    governed_directory.mkdir(parents=True)
    (governed_directory / "page.html").write_text("fixture", encoding="utf-8")
    legacy_wrong_directory = evidence_root / first["id"]
    legacy_wrong_directory.mkdir(parents=True)
    (legacy_wrong_directory / "sentinel.txt").write_text("must remain", encoding="utf-8")

    rejected = client.post(
        f"/api/professional-intelligence/capture-runs/{first['id']}/delete",
        json={"confirmation_phrase": "delete"},
    )
    assert rejected.status_code == 409
    assert governed_directory.exists()

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
    assert not (evidence_root / "professional-intelligence" / first["id"]).exists()
    assert legacy_wrong_directory.exists()

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


def test_capture_run_commit_failure_preserves_governed_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from jolt.database import create_session_factory
    from jolt.professional_intelligence_capture_deletion import (
        DELETE_CAPTURE_CONFIRMATION_PHRASE,
        ProfessionalCaptureDeletionRequest,
        delete_professional_capture_run,
    )
    from jolt.professional_intelligence_records import ProfessionalCaptureRun

    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))
    created = client.post("/api/professional-intelligence/capture-runs").json()

    evidence_root = Path(
        client.get("/api/professional-intelligence/evidence-root").json()["root_path"]
    )

    governed_directory = (
        evidence_root / "professional-intelligence" / created["id"] / "linkedin-profile"
    )
    governed_directory.mkdir(parents=True)
    evidence_file = governed_directory / "page.html"
    evidence_file.write_text("must survive", encoding="utf-8")

    factory = create_session_factory(database_url)

    with factory() as session:

        def failing_commit() -> None:
            raise RuntimeError("simulated database commit failure")

        monkeypatch.setattr(session, "commit", failing_commit)

        request = ProfessionalCaptureDeletionRequest(
            confirmation_phrase=DELETE_CAPTURE_CONFIRMATION_PHRASE,
        )

        try:
            delete_professional_capture_run(
                session,
                created["id"],
                request,
            )
        except RuntimeError as exc:
            assert str(exc) == "simulated database commit failure"
        else:
            raise AssertionError("Expected simulated commit failure.")

    assert governed_directory.exists()
    assert evidence_file.exists()
    assert evidence_file.read_text(encoding="utf-8") == "must survive"

    with factory() as session:
        retained_run = session.get(
            ProfessionalCaptureRun,
            created["id"],
        )

    assert retained_run is not None
