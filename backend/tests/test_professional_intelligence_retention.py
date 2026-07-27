from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from jolt.database import create_session_factory, utc_now
from jolt.main import create_app
from jolt.professional_intelligence_records import ProfessionalCaptureArtifact
from jolt.professional_intelligence_retention import RETENTION_CLEANUP_CONFIRMATION_PHRASE


def _configured_client(tmp_path: Path) -> tuple[TestClient, str, Path]:
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
    return client, database_url, evidence_root / "professional-intelligence" / run["id"]


def _add_artifact(
    database_url: str,
    *,
    run_id: str,
    source_id: str,
    filename: str,
    created_at: datetime,
    retention_days: int,
) -> str:
    artifact_id = str(uuid4())
    factory = create_session_factory(database_url)
    with factory() as session:
        session.add(
            ProfessionalCaptureArtifact(
                id=artifact_id,
                capture_run_id=run_id,
                source_id=source_id,
                artifact_type="page_diagnostics_json",
                relative_path=(f"professional-intelligence/{run_id}/{source_id}/{filename}"),
                sha256="a" * 64,
                completeness_status="complete",
                retention_days=retention_days,
                created_at=created_at,
            )
        )
        session.commit()
    return artifact_id


def test_retention_preview_and_cleanup_are_supervised_and_expiry_scoped(
    tmp_path: Path,
) -> None:
    client, database_url, run_root = _configured_client(tmp_path)
    run_id = run_root.name
    expired_path = run_root / "expired" / "page-diagnostics.json"
    expired_staged = expired_path.with_name(f"{expired_path.name}.staged")
    fresh_path = run_root / "fresh" / "page-diagnostics.json"
    expired_path.parent.mkdir(parents=True)
    fresh_path.parent.mkdir(parents=True)
    expired_path.write_bytes(b"expired-final")
    expired_staged.write_bytes(b"expired-staged")
    fresh_path.write_bytes(b"fresh")

    expired_id = _add_artifact(
        database_url,
        run_id=run_id,
        source_id="expired",
        filename=expired_path.name,
        created_at=utc_now() - timedelta(days=31),
        retention_days=30,
    )
    fresh_id = _add_artifact(
        database_url,
        run_id=run_id,
        source_id="fresh",
        filename=fresh_path.name,
        created_at=utc_now() - timedelta(days=29),
        retention_days=30,
    )
    missing_id = _add_artifact(
        database_url,
        run_id=run_id,
        source_id="missing",
        filename="missing.json",
        created_at=utc_now() - timedelta(days=31),
        retention_days=30,
    )

    preview = client.get("/api/professional-intelligence/retention-preview")
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["confirmation_phrase"] == RETENTION_CLEANUP_CONFIRMATION_PHRASE
    assert payload["expired_artifact_count"] == 2
    assert payload["existing_file_count"] == 2
    assert payload["existing_bytes"] == len(b"expired-final") + len(b"expired-staged")
    assert {candidate["artifact_id"] for candidate in payload["candidates"]} == {
        expired_id,
        missing_id,
    }

    rejected = client.post(
        "/api/professional-intelligence/retention-cleanup",
        json={"confirmation_phrase": "delete it"},
    )
    assert rejected.status_code == 422
    assert expired_path.exists()
    assert expired_staged.exists()
    assert fresh_path.exists()

    cleaned = client.post(
        "/api/professional-intelligence/retention-cleanup",
        json={"confirmation_phrase": RETENTION_CLEANUP_CONFIRMATION_PHRASE},
    )
    assert cleaned.status_code == 200
    result = cleaned.json()
    assert result["deleted_artifact_count"] == 2
    assert result["deleted_file_count"] == 2
    assert result["deleted_bytes"] == len(b"expired-final") + len(b"expired-staged")
    assert not expired_path.exists()
    assert not expired_staged.exists()
    assert fresh_path.exists()

    factory = create_session_factory(database_url)
    with factory() as session:
        remaining_ids = set(session.scalars(select(ProfessionalCaptureArtifact.id)).all())
    assert expired_id not in remaining_ids
    assert missing_id not in remaining_ids
    assert fresh_id in remaining_ids

    after = client.get("/api/professional-intelligence/retention-preview").json()
    assert after["expired_artifact_count"] == 0
    assert after["existing_file_count"] == 0


def test_retention_preview_requires_verified_evidence_root(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    response = client.get("/api/professional-intelligence/retention-preview")

    assert response.status_code == 422
    assert "verified writable local evidence root" in response.json()["detail"]
