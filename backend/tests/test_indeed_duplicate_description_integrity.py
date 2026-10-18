from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from jolt.database import Posting, create_session_factory
from jolt.discovery_execution import (
    DiscoveryExecutionCreateRequest,
    create_discovery_execution,
    execute_discovery_execution,
    get_discovery_execution,
    recover_interrupted_discovery_executions,
)
from jolt.discovery_searches import DiscoverySavedSearchRequest, create_discovery_search
from jolt.main import create_app


def test_indeed_duplicate_does_not_replace_full_description_with_shorter_capture(
    tmp_path: Path,
) -> None:
    db = tmp_path / "indeed-integrity.db"
    url = f"sqlite:///{db.as_posix()}"
    client = TestClient(create_app(url))
    full = "Maintain Windows endpoints, investigate SQL incidents, review logs and APIs."
    short = "Maintain Windows endpoints."
    payload = {
        "search_url": "https://es.indeed.com/jobs?q=it+support",
        "items": [
            {
                "source_job_id": "integrity-123",
                "source_url": "https://es.indeed.com/viewjob?jk=integrity-123",
                "title": "IT Support",
                "company": "Example Systems",
                "location": "Vigo",
                "description": full,
                "identity_verified": True,
                "verification_reason": "",
            }
        ],
    }
    first = client.post("/api/captures/indeed/live", json=payload)
    assert first.status_code == 200
    first_item = first.json()["items"][0]
    assert first_item["identity_status"] == "new"

    payload["items"][0]["description"] = short
    second = client.post("/api/captures/indeed/live", json=payload)
    assert second.status_code == 200
    second_item = second.json()["items"][0]
    assert second_item["identity_status"] == "confirmed_duplicate"
    assert second_item["posting_id"] == first_item["posting_id"]
    assert second_item["source_document_id"] != first_item["source_document_id"]

    with create_session_factory(url)() as session:
        postings = session.scalars(select(Posting)).all()
        assert len(postings) == 1
        assert postings[0].description == full

    exchange = client.get("/api/ai-work-package/export")
    assert exchange.status_code == 200
    review_inbox = exchange.json()["review_inbox"]
    assert review_inbox is not None
    assert any(
        job["posting_id"] == first_item["posting_id"]
        and full in job["analysis_text"]
        for job in review_inbox["jobs"]
    )

    restarted = TestClient(create_app(url))
    assert restarted.get("/api/opportunities").status_code == 200
    with create_session_factory(url)() as session:
        assert session.get(Posting, first_item["posting_id"]).description == full


def test_indeed_capture_ai_review_round_trip_survives_restart(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'indeed-review.db').as_posix()}"
    client = TestClient(create_app(url))
    captured = client.post(
        "/api/captures/indeed/live",
        json={
            "search_url": "https://es.indeed.com/jobs?q=application+support",
            "requested_item_limit": 1,
            "items": [
                {
                    "source_job_id": "review-123",
                    "source_url": "https://es.indeed.com/viewjob?jk=review-123",
                    "title": "Application Support Engineer",
                    "company": "Example Systems",
                    "location": "Spain",
                    "description": "Provide application support, SQL analysis and incident resolution.",
                    "identity_verified": True,
                    "verification_reason": "",
                }
            ],
        },
    )
    assert captured.status_code == 200
    item = captured.json()["items"][0]
    assert item["detail_status"] == "verified"
    inbox_before = client.get("/api/ai-review/opportunity-index")
    assert inbox_before.status_code == 200
    assert any(
        row["posting_id"] == item["posting_id"]
        and row["ai_review_status"] == "awaiting_ai_review"
        for row in inbox_before.json()
    )
    work_package = client.get("/api/ai-work-package/export")
    assert work_package.status_code == 200
    assert item["posting_id"] in {
        job["posting_id"] for job in work_package.json()["review_inbox"]["jobs"]
    }
    imported = client.post(
        "/api/ai-review/import",
        json={
            "contract_type": "jolt_ai_review",
            "contract_version": "1.0",
            "capture_run_id": captured.json()["capture_run_id"],
            "review_source": "chatgpt_source_first",
            "review_version": "indeed-fixture-1",
            "reviewed_at": "2026-10-18T12:00:00+00:00",
            "jobs": [
                {
                    "posting_id": item["posting_id"],
                    "source_job_id": item["source_job_id"],
                    "decision": "reject",
                    "priority_score": 20,
                    "geography_status": "eligible",
                    "clearance_status": "clear",
                    "language_status": "clear",
                    "technical_fit": None,
                    "duplicate_of_posting_id": None,
                    "summary": "Fixture decision; not a real candidate assessment.",
                    "reasons": ["Regression test of the Indeed AI import path."],
                }
            ],
        },
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["created_count"] == 1

    restarted = TestClient(create_app(url))
    inbox_after = restarted.get("/api/ai-review/opportunity-index")
    assert inbox_after.status_code == 200
    reviewed = next(
        row for row in inbox_after.json() if row["posting_id"] == item["posting_id"]
    )
    assert reviewed["ai_review_status"] == "reviewed"
    assert reviewed["decision"] == "reject"


def test_indeed_discovery_failure_and_restart_recovery_are_truthful(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'indeed-execution.db').as_posix()}"
    factory = create_session_factory(url)
    with factory() as session:
        search = create_discovery_search(
            session,
            DiscoverySavedSearchRequest(
                source="indeed",
                label="Indeed acceptance fixture",
                definition={"search_url": "https://es.indeed.com/jobs?q=support"},
                enabled=True,
                max_jobs=5,
            ),
        )
        execution = create_discovery_execution(
            session,
            DiscoveryExecutionCreateRequest(
                source="indeed",
                saved_search_id=search.id,
            ),
        )

        def fail_capture(_search: object, _execution_id: str) -> str:
            raise RuntimeError("Simulated Indeed portal block")

        with pytest.raises(RuntimeError, match="Simulated Indeed portal block"):
            execute_discovery_execution(session, execution.id, runner=fail_capture)

        failed = get_discovery_execution(session, execution.id)
        assert failed.status == "failed"
        assert "Simulated Indeed portal block" in failed.error

        interrupted = create_discovery_execution(
            session,
            DiscoveryExecutionCreateRequest(
                source="indeed",
                saved_search_id=search.id,
            ),
        )
        assert interrupted.status == "queued"

    with factory() as restarted:
        assert recover_interrupted_discovery_executions(restarted) == 1
        assert get_discovery_execution(restarted, execution.id).status == "failed"
        recovered = get_discovery_execution(restarted, interrupted.id)
        assert recovered.status == "failed"
        assert "interrupted" in recovered.error.lower()
