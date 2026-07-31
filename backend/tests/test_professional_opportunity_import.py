from __future__ import annotations

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


def _client_and_factory(tmp_path: Path):
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    return TestClient(create_app(database_url)), create_session_factory(database_url)


def _write_rendered_text_artifact(
    *,
    root: Path,
    run_id: str,
    source_id: str,
    source_url: str,
    text: str,
) -> tuple[str, str]:
    content = json.dumps(
        {
            "source_id": source_id,
            "source_url": source_url,
            "extraction_method": "visible_rendered_dom_text",
            "derived": False,
            "text": text,
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    relative_path = f"professional-intelligence/{run_id}/{source_id}/rendered-text.json"
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return relative_path, hashlib.sha256(content).hexdigest()


def _complete_run_with_rendered_text(factory, run: dict, evidence_root: Path) -> None:
    with factory() as session:
        stored = session.get(ProfessionalCaptureRun, run["id"])
        assert stored is not None
        stored.status = "completed"
        stored.completed_at = utc_now()
        stored.completed_source_count = len(run["planned_sources"])
        stored.current_source_id = ""
        stored.stop_reason = ""

        for source in run["planned_sources"]:
            if source["category"] == "career":
                text = "\n".join(
                    [
                        "Jobs based on your preferences",
                        "Application Support Engineer",
                        "Acme SaaS Operations",
                        "Remote Spain",
                        "Troubleshoot SQL incidents, API integrations, logs, RCA, Microsoft 365 and Windows application support.",
                        "Technical Support Engineer",
                        "Contoso Cloud Services",
                        "Hybrid Galicia",
                        "Support enterprise users with Azure, DNS, PowerShell, ServiceNow and production incidents.",
                    ]
                )
            else:
                text = f"Captured profile evidence for {source['label']}. Microsoft 365, Entra ID, Active Directory and IT operations."
            relative_path, sha256 = _write_rendered_text_artifact(
                root=evidence_root,
                run_id=run["id"],
                source_id=source["source_id"],
                source_url=source["url"],
                text=text,
            )
            session.add(
                ProfessionalCaptureArtifact(
                    id=str(uuid4()),
                    capture_run_id=run["id"],
                    source_id=source["source_id"],
                    artifact_type="rendered_text_json",
                    relative_path=relative_path,
                    sha256=sha256,
                    completeness_status="complete",
                    retention_days=30,
                    created_at=utc_now(),
                )
            )
        session.commit()


def test_professional_career_capture_imports_opportunities_to_review_inbox(tmp_path: Path) -> None:
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
    assert any(source["category"] == "career" for source in run["planned_sources"])
    _complete_run_with_rendered_text(factory, run, evidence_root)

    imported = client.post(
        f"/api/professional-intelligence/capture-runs/{run['id']}/opportunity-candidates/import"
    )
    assert imported.status_code == 200
    payload = imported.json()
    assert payload["imported_count"] >= 2
    assert payload["skipped_count"] >= 0
    assert payload["imported_count"] + payload["skipped_count"] >= 2

    imported_titles = {candidate["title"] for candidate in payload["candidates"]}
    assert imported_titles
    assert imported_titles <= {"Application Support Engineer", "Technical Support Engineer"}
    assert any(title in imported_titles for title in {"Application Support Engineer", "Technical Support Engineer"})

    index = client.get("/api/opportunity-index")
    assert index.status_code == 200
    serialized = json.dumps(index.json())
    assert "Application Support Engineer" in serialized or "Technical Support Engineer" in serialized


def test_professional_opportunity_import_rejects_unready_run(tmp_path: Path) -> None:
    client, _factory = _client_and_factory(tmp_path)
    created = client.post("/api/professional-intelligence/capture-runs")
    assert created.status_code == 200
    run = created.json()

    imported = client.post(
        f"/api/professional-intelligence/capture-runs/{run['id']}/opportunity-candidates/import"
    )

    assert imported.status_code == 422
