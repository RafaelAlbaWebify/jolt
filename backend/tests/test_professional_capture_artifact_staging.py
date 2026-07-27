from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from jolt.database import create_session_factory
from jolt.main import create_app
from jolt.professional_intelligence_capture_runs import AUTHORIZATION_CONFIRMATION_PHRASE
from jolt.professional_intelligence_records import ProfessionalCaptureArtifact
from jolt.professional_intelligence_supervised_capture import (
    CapturedProfessionalPage,
    reconcile_professional_capture_artifacts,
    start_professional_supervised_capture,
)


def _authorized_run(tmp_path: Path) -> tuple[str, str, Path]:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    client = TestClient(create_app(database_url))
    configured = client.post(
        "/api/professional-intelligence/evidence-root",
        json={"root_path": str(evidence_root)},
    )
    assert configured.status_code == 200
    run = client.post("/api/professional-intelligence/capture-runs").json()
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


def test_successful_capture_finalizes_every_staged_artifact(tmp_path: Path) -> None:
    database_url, run_id, evidence_root = _authorized_run(tmp_path)
    factory = create_session_factory(database_url)

    with factory() as session:
        completed = start_professional_supervised_capture(
            session, run_id, capture_source=_fixture_page
        )
        assert completed.status == "completed"

    professional_root = evidence_root / "professional-intelligence"
    assert list(professional_root.rglob("*.staged")) == []
    assert len([path for path in professional_root.rglob("*") if path.is_file()]) == 32


def test_reconciliation_finalizes_manifested_stage_and_removes_orphans(
    tmp_path: Path,
) -> None:
    database_url, run_id, evidence_root = _authorized_run(tmp_path)
    factory = create_session_factory(database_url)

    with factory() as session:
        start_professional_supervised_capture(session, run_id, capture_source=_fixture_page)
        artifact = session.scalars(
            select(ProfessionalCaptureArtifact).where(
                ProfessionalCaptureArtifact.capture_run_id == run_id
            )
        ).first()
        assert artifact is not None
        final_path = evidence_root / Path(*artifact.relative_path.split("/"))
        staged_path = final_path.with_name(f"{final_path.name}.staged")
        final_path.replace(staged_path)

        orphan_final = final_path.parent / "orphan.json"
        orphan_stage = final_path.parent / "orphan-stage.json.staged"
        orphan_final.write_text("orphan", encoding="utf-8")
        orphan_stage.write_text("orphan", encoding="utf-8")

        reconcile_professional_capture_artifacts(session, evidence_root)

    assert final_path.is_file()
    assert not staged_path.exists()
    assert not orphan_final.exists()
    assert not orphan_stage.exists()


def test_precommit_failure_discards_staged_files_and_manifest_rows(
    tmp_path: Path, monkeypatch
) -> None:
    database_url, run_id, evidence_root = _authorized_run(tmp_path)
    factory = create_session_factory(database_url)

    from jolt import professional_intelligence_supervised_capture as capture_module

    original_write = capture_module._write_artifact
    calls = 0

    def fail_after_first_write(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OSError("fixture staged write failure")
        return original_write(*args, **kwargs)

    monkeypatch.setattr(capture_module, "_write_artifact", fail_after_first_write)

    with (
        factory() as session,
        pytest.raises(OSError, match="fixture staged write failure"),
    ):
        start_professional_supervised_capture(session, run_id, capture_source=_fixture_page)

    with factory() as session:
        artifact_count = session.scalar(
            select(func.count(ProfessionalCaptureArtifact.id)).where(
                ProfessionalCaptureArtifact.capture_run_id == run_id
            )
        )
        assert artifact_count == 0

    run_root = evidence_root / "professional-intelligence" / run_id
    assert not run_root.exists() or not any(path.is_file() for path in run_root.rglob("*"))
