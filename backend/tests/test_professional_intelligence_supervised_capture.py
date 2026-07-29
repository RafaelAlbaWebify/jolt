from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from jolt.database import create_session_factory
from jolt.main import create_app
from jolt.professional_intelligence_capture_runs import AUTHORIZATION_CONFIRMATION_PHRASE
from jolt.professional_intelligence_records import ProfessionalCaptureArtifact
from jolt.professional_intelligence_supervised_capture import (
    CapturedProfessionalPage,
    start_professional_supervised_capture,
)


def _authorized_run(tmp_path: Path, *, stop_on_failure: bool = True) -> tuple[str, str, Path]:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    client = TestClient(create_app(database_url))
    configured = client.post(
        "/api/professional-intelligence/evidence-root",
        json={"root_path": str(evidence_root)},
    )
    assert configured.status_code == 200
    run = client.post(
        "/api/professional-intelligence/capture-runs",
        json={"options": {"stop_on_failure": stop_on_failure}},
    ).json()
    authorized = client.post(
        f"/api/professional-intelligence/capture-runs/{run['id']}/authorize",
        json={
            "confirmation_phrase": AUTHORIZATION_CONFIRMATION_PHRASE,
            "user_present": True,
        },
    )
    assert authorized.status_code == 200
    return database_url, run["id"], evidence_root


def _fixture_page(url: str) -> CapturedProfessionalPage:
    return CapturedProfessionalPage(
        screenshot_png=b"fixture-png-bytes",
        visible_text=(f"Visible rendered profile evidence from {url}. " * 5),
        title="Fixture LinkedIn page",
        final_url=url,
        http_status=200,
    )


def test_supervised_capture_writes_contained_verified_artifacts(tmp_path: Path) -> None:
    database_url, run_id, evidence_root = _authorized_run(tmp_path)
    factory = create_session_factory(database_url)
    with factory() as session:
        completed = start_professional_supervised_capture(
            session, run_id, capture_source=_fixture_page
        )
        assert completed.status == "completed"
        assert completed.artifact_count == 32
        assert completed.started_at is not None
        assert completed.completed_at is not None

        artifacts = session.scalars(
            select(ProfessionalCaptureArtifact).where(
                ProfessionalCaptureArtifact.capture_run_id == run_id
            )
        ).all()
        assert len(artifacts) == 32
        assert {artifact.completeness_status for artifact in artifacts} == {"complete"}
        assert all(len(artifact.sha256) == 64 for artifact in artifacts)
        assert all(artifact.retention_days == 30 for artifact in artifacts)

    run_root = evidence_root / "professional-intelligence" / run_id
    assert run_root.is_dir()
    source_directories = [path for path in run_root.iterdir() if path.is_dir()]
    assert len(source_directories) == 8
    assert all((path / "page.png").is_file() for path in source_directories)
    assert all((path / "rendered-text.json").is_file() for path in source_directories)
    assert all((path / "capture-metadata.json").is_file() for path in source_directories)
    assert all((path / "page-diagnostics.json").is_file() for path in source_directories)


def test_supervised_capture_records_source_failure_and_continues(tmp_path: Path) -> None:
    database_url, run_id, evidence_root = _authorized_run(tmp_path, stop_on_failure=False)
    calls = 0

    def capture_source(url: str) -> CapturedProfessionalPage:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("fixture navigation failed")
        return _fixture_page(url)

    factory = create_session_factory(database_url)
    with factory() as session:
        completed = start_professional_supervised_capture(
            session, run_id, capture_source=capture_source
        )
        assert completed.status == "completed_with_gaps"
        assert completed.stop_reason == "one_or_more_sources_partial_or_failed"
        assert completed.artifact_count == 29

    diagnostics = list(
        (evidence_root / "professional-intelligence" / run_id).glob("*/page-diagnostics.json")
    )
    assert len(diagnostics) == 8
    assert any(
        "fixture navigation failed" in path.read_text(encoding="utf-8") for path in diagnostics
    )


def test_supervised_capture_marks_engine_failure_instead_of_staying_running(
    tmp_path: Path, monkeypatch
) -> None:
    database_url, run_id, _evidence_root = _authorized_run(tmp_path)
    factory = create_session_factory(database_url)

    def fail_write(*args, **kwargs) -> None:
        raise OSError("fixture storage failure")

    monkeypatch.setattr(
        "jolt.professional_intelligence_supervised_capture._write_artifact",
        fail_write,
    )
    with (
        factory() as session,
        pytest.raises(OSError, match="fixture storage failure"),
    ):
        start_professional_supervised_capture(session, run_id, capture_source=_fixture_page)

    client = TestClient(create_app(database_url))
    failed = client.get(f"/api/professional-intelligence/capture-runs/{run_id}").json()
    assert failed["status"] == "failed"
    assert failed["stop_reason"] == "capture_engine_failure"
    assert failed["completed_at"] is not None
    assert failed["current_source_id"] == ""
