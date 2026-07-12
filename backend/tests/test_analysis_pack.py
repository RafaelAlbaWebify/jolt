from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{path.as_posix()}"))


def test_analysis_pack_contains_auditable_evidence_chain(tmp_path: Path) -> None:
    client = _client(tmp_path / "analysis.db")
    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.com/jobs/analysis-1?utm_source=test",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Application support, SQL, incident ownership and API troubleshooting."
            ),
        },
    ).json()
    client.post(
        f"/api/opportunities/{intake['posting_id']}/reviews",
        json={"evaluation_id": intake["evaluation_id"], "decision": "pursue"},
    )
    application = client.post(
        f"/api/opportunities/{intake['posting_id']}/applications",
        json={"resume_used": "application-support-v1.pdf"},
    ).json()
    client.post(
        f"/api/applications/{application['application_id']}/transitions",
        json={"status": "submitted", "notes": "Submitted on employer site."},
    )
    client.post(
        f"/api/applications/{application['application_id']}/outcomes",
        json={
            "outcome_type": "rejected_by_employer",
            "reason_code": "no_feedback",
            "notes": "Standard rejection email.",
        },
    )

    response = client.get("/api/exports/analysis-pack")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "JOLT_ANALYSIS_PACK.zip" in response.headers["content-disposition"]

    with ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert {
            "README.md",
            "manifest.json",
            "data/full_dataset.json",
            "data/opportunities.csv",
            "data/evaluations.csv",
            "data/reviews.csv",
            "data/applications.csv",
            "data/application_events.csv",
            "data/outcomes.csv",
            "feedback/feedback_template.json",
        }.issubset(names)

        dataset = json.loads(archive.read("data/full_dataset.json"))
        assert dataset["pack_version"] == "1.0"
        data = dataset["data"]
        assert len(data["source_documents"]) == 1
        assert data["postings"][0]["title"] == "Application Support Engineer"
        assert data["evaluations"][0]["recommendation"] == "pursue"
        assert data["review_decisions"][0]["decision"] == "pursue"
        assert data["applications"][0]["status"] == "rejected"
        assert [event["to_status"] for event in data["application_events"]] == [
            "preparing",
            "submitted",
            "rejected",
        ]
        assert data["outcomes"][0]["outcome_type"] == "rejected_by_employer"
        assert data["outcomes"][0]["stage_reached"] == "submitted"

        feedback = json.loads(archive.read("feedback/feedback_template.json"))
        assert feedback["approval_required"] is True
        assert feedback["profile_recommendations"] == []

        summary = archive.read("README.md").decode("utf-8")
        assert "Canonical postings: 1" in summary
        assert "Employer rejections: 1" in summary
        assert "Do not infer rule quality from small samples" in summary

        manifest = json.loads(archive.read("manifest.json"))
        for name, metadata in manifest["files"].items():
            content = archive.read(name)
            assert metadata["bytes"] == len(content)
            assert metadata["sha256"] == hashlib.sha256(content).hexdigest()
