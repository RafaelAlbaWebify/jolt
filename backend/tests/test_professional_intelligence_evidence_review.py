import hashlib
import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from jolt.database import create_session_factory, utc_now
from jolt.main import create_app
from jolt.professional_intelligence_records import (
    ProfessionalCaptureArtifact,
    ProfessionalCaptureRun,
)


def _completed_run_with_evidence(tmp_path: Path) -> tuple[TestClient, str, Path]:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    client = TestClient(create_app(database_url))
    assert client.post(
        "/api/professional-intelligence/evidence-root",
        json={"root_path": str(evidence_root)},
    ).status_code == 200
    run = client.post("/api/professional-intelligence/capture-runs").json()
    run_id = run["id"]
    source = run["planned_sources"][0]
    source_id = source["source_id"]
    source_root = evidence_root / "professional-intelligence" / run_id / source_id
    source_root.mkdir(parents=True)

    payloads = {
        "rendered_text_json": (
            "rendered-text.json",
            json.dumps({"source_id": source_id, "text": "Visible professional evidence"}).encode(),
        ),
        "capture_metadata_json": (
            "capture-metadata.json",
            json.dumps({"source_id": source_id, "title": "Fixture profile"}).encode(),
        ),
        "page_diagnostics_json": (
            "page-diagnostics.json",
            json.dumps({"source_id": source_id, "completeness_status": "complete"}).encode(),
        ),
        "screenshot_png": ("page.png", b"fixture-png"),
    }
    factory = create_session_factory(database_url)
    with factory() as session:
        stored_run = session.get(ProfessionalCaptureRun, run_id)
        assert stored_run is not None
        stored_run.status = "completed"
        stored_run.mode = "supervised_read_only"
        stored_run.started_at = utc_now()
        stored_run.completed_at = utc_now()
        for artifact_type, (filename, content) in payloads.items():
            (source_root / filename).write_bytes(content)
            session.add(
                ProfessionalCaptureArtifact(
                    id=str(uuid4()),
                    capture_run_id=run_id,
                    source_id=source_id,
                    artifact_type=artifact_type,
                    relative_path=(
                        f"professional-intelligence/{run_id}/{source_id}/{filename}"
                    ),
                    sha256=hashlib.sha256(content).hexdigest(),
                    completeness_status="complete",
                    retention_days=30,
                    created_at=utc_now(),
                )
            )
        session.commit()
    return client, run_id, source_root


def test_evidence_review_verifies_integrity_and_exposes_json_only(tmp_path: Path) -> None:
    client, run_id, _source_root = _completed_run_with_evidence(tmp_path)

    response = client.get(
        f"/api/professional-intelligence/capture-runs/{run_id}/evidence-review"
    )

    assert response.status_code == 200
    review = response.json()
    assert review["run_status"] == "completed"
    assert review["integrity_valid"] is True
    assert review["review_available"] is True
    assert review["ready_for_analysis"] is True
    artifacts = review["sources"][0]["artifacts"]
    screenshot = next(item for item in artifacts if item["artifact_type"] == "screenshot_png")
    rendered = next(item for item in artifacts if item["artifact_type"] == "rendered_text_json")
    assert screenshot["reviewable"] is False
    assert screenshot["content"] is None
    assert rendered["reviewable"] is True
    assert rendered["content"]["text"] == "Visible professional evidence"


def test_evidence_review_detects_tampering(tmp_path: Path) -> None:
    client, run_id, source_root = _completed_run_with_evidence(tmp_path)
    (source_root / "rendered-text.json").write_text("tampered", encoding="utf-8")

    review = client.get(
        f"/api/professional-intelligence/capture-runs/{run_id}/evidence-review"
    ).json()

    assert review["integrity_valid"] is False
    assert review["ready_for_analysis"] is False
    rendered = next(
        item
        for item in review["sources"][0]["artifacts"]
        if item["artifact_type"] == "rendered_text_json"
    )
    assert rendered["exists"] is True
    assert rendered["integrity_valid"] is False
    assert rendered["content"] is None


def test_evidence_review_requires_configured_root_and_known_run(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))
    run = client.post("/api/professional-intelligence/capture-runs").json()

    missing_root = client.get(
        f"/api/professional-intelligence/capture-runs/{run['id']}/evidence-review"
    )
    unknown_run = client.get(
        "/api/professional-intelligence/capture-runs/missing/evidence-review"
    )

    assert missing_root.status_code == 422
    assert unknown_run.status_code == 404
