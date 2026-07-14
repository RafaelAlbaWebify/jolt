from __future__ import annotations

import hashlib
import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from jolt.capture_artifacts import CaptureArtifact
from jolt.database import CaptureItem, Posting, SourceDocument, create_session_factory
from jolt.main import create_app


def test_live_capture_preserves_auditable_evidence_chain(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'capture-evidence.db').as_posix()}"
    client = TestClient(create_app(database_url))

    verified_item = {
        "source_job_id": "4434979232",
        "source_url": "https://www.linkedin.com/jobs/view/4434979232",
        "title": "Application Support Engineer",
        "company": "Example Systems",
        "location": "Remote Spain",
        "description": (
            "Support production applications, SQL diagnostics, APIs, integrations, "
            "incident response, and controlled escalation."
        ),
        "identity_verified": True,
        "verification_reason": "Detail panel matched the selected LinkedIn job ID.",
    }
    rejected_item = {
        "source_job_id": "4435000001",
        "source_url": "https://www.linkedin.com/jobs/view/4435000001",
        "title": "Production Support Engineer",
        "company": "Unverified Systems",
        "location": "European Union",
        "description": "This text must not become a canonical posting.",
        "identity_verified": False,
        "verification_reason": "Detail panel did not match the selected LinkedIn job ID.",
    }

    response = client.post(
        "/api/captures/linkedin/live",
        json={
            "search_url": "https://www.linkedin.com/jobs/search/?keywords=application%20support",
            "requested_item_limit": 2,
            "stop_reason": "requested_limit_reached",
            "items": [verified_item, rejected_item],
        },
    )

    assert response.status_code == 200
    capture = response.json()
    assert capture["source"] == "linkedin"
    assert capture["mode"] == "supervised_live"
    assert capture["status"] == "completed_with_warnings"
    assert capture["requested_item_limit"] == 2
    assert capture["observed_item_count"] == 2
    assert capture["stop_reason"] == "requested_limit_reached"
    assert capture["total_items"] == 2
    assert capture["verified_items"] == 1
    assert capture["rejected_items"] == 1
    assert capture["pages"][0]["visible_job_ids"] == ["4434979232", "4435000001"]

    verified_response, rejected_response = capture["items"]
    assert verified_response["detail_status"] == "verified"
    assert verified_response["posting_id"]
    assert verified_response["source_document_id"]
    assert verified_response["identity_status"] == "new"
    assert rejected_response["detail_status"] == "rejected_unverified"
    assert rejected_response["posting_id"] is None
    assert rejected_response["source_document_id"] is None
    assert rejected_response["identity_status"] is None

    for item in capture["items"]:
        assert item["artifact_id"]
        assert len(item["artifact_hash"]) == 64
        assert "raw_payload" not in item

    summaries = client.get("/api/captures")
    assert summaries.status_code == 200
    assert summaries.json() == [
        {key: value for key, value in capture.items() if key not in {"pages", "items"}}
    ]

    detail = client.get(f"/api/captures/{capture['capture_run_id']}")
    assert detail.status_code == 200
    assert detail.json() == capture
    assert "raw_payload" not in json.dumps(detail.json())

    opportunities = client.get("/api/opportunities")
    assert opportunities.status_code == 200
    assert len(opportunities.json()) == 1
    assert opportunities.json()[0]["posting_id"] == verified_response["posting_id"]

    session_factory = create_session_factory(database_url)
    with session_factory() as session:
        capture_items = session.scalars(
            select(CaptureItem).order_by(CaptureItem.source_job_id)
        ).all()
        artifacts = session.scalars(
            select(CaptureArtifact).order_by(CaptureArtifact.capture_item_id)
        ).all()
        postings = session.scalars(select(Posting)).all()
        source_documents = session.scalars(select(SourceDocument)).all()

        assert len(capture_items) == 2
        assert len(artifacts) == 2
        assert len(postings) == 1
        assert len(source_documents) == 1

        artifacts_by_item = {
            artifact.capture_item_id: artifact for artifact in artifacts
        }
        request_items = {
            verified_item["source_job_id"]: verified_item,
            rejected_item["source_job_id"]: rejected_item,
        }
        responses_by_job = {item["source_job_id"]: item for item in capture["items"]}

        for capture_item in capture_items:
            artifact = artifacts_by_item[capture_item.id]
            expected_payload = json.dumps(
                request_items[capture_item.source_job_id], sort_keys=True
            )
            expected_hash = hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()

            assert artifact.artifact_type == "linkedin_live_item_json"
            assert artifact.content_type == "application/json"
            assert artifact.raw_payload == expected_payload
            assert artifact.content_hash == expected_hash
            assert (
                responses_by_job[capture_item.source_job_id]["artifact_id"]
                == artifact.id
            )
            assert (
                responses_by_job[capture_item.source_job_id]["artifact_hash"]
                == artifact.content_hash
            )

        verified_row = next(
            item
            for item in capture_items
            if item.source_job_id == verified_item["source_job_id"]
        )
        rejected_row = next(
            item
            for item in capture_items
            if item.source_job_id == rejected_item["source_job_id"]
        )
        assert verified_row.posting_id == postings[0].id
        assert verified_row.source_document_id == source_documents[0].id
        assert rejected_row.posting_id is None
        assert rejected_row.source_document_id is None
