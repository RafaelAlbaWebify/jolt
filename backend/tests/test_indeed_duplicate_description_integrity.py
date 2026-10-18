from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from jolt.database import Posting, create_session_factory
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
