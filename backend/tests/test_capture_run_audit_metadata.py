# ruff: noqa: I001

from pathlib import Path

from fastapi.testclient import TestClient
from jolt.main import create_app


def test_live_capture_records_requested_bound_and_stop_reason(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    response = client.post(
        "/api/captures/linkedin/live",
        json={
            "search_url": "https://www.linkedin.com/jobs/search/?keywords=support",
            "requested_item_limit": 3,
            "stop_reason": "requested_limit_reached",
            "items": [
                {
                    "source_job_id": "1001",
                    "source_url": "https://www.linkedin.com/jobs/view/1001",
                    "title": "Application Support Engineer",
                    "company": "Example Ltd",
                    "location": "Remote",
                    "description": "Application support, SQL, incident ownership and APIs.",
                    "identity_verified": True,
                    "verification_reason": "Detail identity matched the selected card.",
                },
                {
                    "source_job_id": "1002",
                    "source_url": "https://www.linkedin.com/jobs/view/1002",
                    "title": "Infrastructure Support Engineer",
                    "company": "Example Ltd",
                    "location": "Spain",
                    "description": "Infrastructure, automation and production support.",
                    "identity_verified": True,
                    "verification_reason": "Detail identity matched the selected card.",
                },
                {
                    "source_job_id": "1003",
                    "source_url": "https://www.linkedin.com/jobs/view/1003",
                    "title": "Technical Support Engineer",
                    "company": "Example Ltd",
                    "location": "Europe",
                    "description": "Technical support, integrations and incident response.",
                    "identity_verified": True,
                    "verification_reason": "Detail identity matched the selected card.",
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_item_limit"] == 3
    assert payload["observed_item_count"] == 3
    assert payload["stop_reason"] == "requested_limit_reached"
    assert payload["total_items"] == 3

    history = client.get("/api/captures")
    assert history.status_code == 200
    summary = history.json()[0]
    assert summary["requested_item_limit"] == 3
    assert summary["observed_item_count"] == 3
    assert summary["stop_reason"] == "requested_limit_reached"


def test_live_capture_derives_auditable_defaults(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt-defaults.db').as_posix()}"
    client = TestClient(create_app(database_url))

    response = client.post(
        "/api/captures/linkedin/live",
        json={
            "items": [
                {
                    "source_job_id": "2001",
                    "title": "Support Engineer",
                    "company": "Example Ltd",
                    "description": "Production support and incident ownership.",
                    "identity_verified": True,
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_item_limit"] == 1
    assert payload["observed_item_count"] == 1
    assert payload["stop_reason"] == "submitted_batch_completed"
