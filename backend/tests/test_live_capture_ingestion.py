from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_verified_live_capture_creates_capture_items_and_opportunities(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'live.db').as_posix()}"))

    response = client.post(
        "/api/captures/linkedin/live",
        json={
            "search_url": "https://www.linkedin.com/jobs/search/?keywords=IT%20Support",
            "items": [
                {
                    "source_job_id": "111",
                    "source_url": "https://www.linkedin.com/jobs/view/111",
                    "title": "Application Support Engineer",
                    "company": "Example Systems",
                    "location": "Remote Spain",
                    "description": "Own SQL application incidents, logs, APIs, and production support.",
                    "identity_verified": True,
                    "verification_reason": "",
                },
                {
                    "source_job_id": "222",
                    "source_url": "https://www.linkedin.com/jobs/view/222",
                    "title": "Stale Listing",
                    "company": "Example Systems",
                    "location": "Spain",
                    "description": "",
                    "identity_verified": False,
                    "verification_reason": "Detail identity did not match.",
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "supervised_live"
    assert payload["total_items"] == 2
    assert payload["verified_items"] == 1
    assert payload["rejected_items"] == 1
    assert payload["items"][0]["posting_id"]
    assert payload["items"][1]["posting_id"] is None

    opportunities = client.get("/api/opportunities")
    assert opportunities.status_code == 200
    assert len(opportunities.json()) == 1
    assert opportunities.json()[0]["title"] == "Application Support Engineer"
