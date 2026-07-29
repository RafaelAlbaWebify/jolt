from fastapi.testclient import TestClient

from jolt.main import create_app


def _capture_payload(title: str, source_job_id: str = "job-1") -> dict[str, object]:
    return {
        "search_url": "https://www.linkedin.com/jobs/search/?keywords=Support",
        "requested_item_limit": 1,
        "items": [
            {
                "source_job_id": source_job_id,
                "source_url": f"https://www.linkedin.com/jobs/view/{source_job_id}/",
                "title": title,
                "company": "Example Co",
                "location": "Spain (Remote)",
                "description": "Application Support role with Windows, SQL, ServiceNow and production support responsibilities.",
                "identity_verified": True,
                "verification_reason": "Fixture identity verified.",
            }
        ],
        "pages": [
            {
                "page_number": 1,
                "visible_job_ids": [source_job_id],
                "next_control_present": False,
                "next_control_enabled": False,
            }
        ],
    }


def test_deleting_capture_batch_removes_unclassified_imported_opportunity(tmp_path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    captured = client.post("/api/captures/linkedin/live", json=_capture_payload("Support Engineer")).json()
    assert captured["verified_items"] == 1
    assert len(client.get("/api/opportunity-index").json()) == 1

    deleted = client.post(f"/api/captures/{captured['capture_run_id']}/delete")
    assert deleted.status_code == 200
    assert deleted.json()["deleted_item_count"] == 1
    assert deleted.json()["deleted_posting_count"] == 1
    assert deleted.json()["deleted_evaluation_count"] == 1
    assert deleted.json()["deleted_source_document_count"] == 1
    assert deleted.json()["protected_posting_count"] == 0
    assert client.get("/api/opportunity-index").json() == []
    assert client.get("/api/application-index").json() == []
    assert client.get("/api/captures").json() == []


def test_deleting_capture_batch_preserves_reviewed_opportunity_outside_review_inbox(tmp_path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    captured = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload("Reviewed Support Engineer", source_job_id="job-reviewed"),
    ).json()
    opportunity = client.get("/api/opportunity-index").json()[0]
    review = client.post(
        f"/api/opportunities/{opportunity['posting_id']}/reviews",
        json={
            "evaluation_id": opportunity["evaluation_id"],
            "decision": "pursue",
            "reason_code": "fit",
            "notes": "Worth tracking.",
        },
    )
    assert review.status_code == 200
    assert client.get("/api/opportunity-index").json() == []

    deleted = client.post(f"/api/captures/{captured['capture_run_id']}/delete")
    assert deleted.status_code == 200
    assert deleted.json()["deleted_item_count"] == 1
    assert deleted.json()["deleted_posting_count"] == 0
    assert deleted.json()["protected_posting_count"] == 1

    assert client.get("/api/opportunity-index").json() == []
    remaining = client.get("/api/application-index").json()
    assert len(remaining) == 1
    assert remaining[0]["posting_id"] == opportunity["posting_id"]
