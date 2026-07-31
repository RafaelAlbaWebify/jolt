from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))


def test_verified_linkedin_job_capture_feeds_review_inbox(tmp_path: Path) -> None:
    client = _client(tmp_path)

    captured = client.post(
        "/api/captures/linkedin/live",
        json={
            "search_url": "https://www.linkedin.com/jobs/search/?keywords=Application%20Support%20Engineer",
            "requested_item_limit": 1,
            "items": [
                {
                    "source_job_id": "linkedin-job-1",
                    "source_url": "https://www.linkedin.com/jobs/view/linkedin-job-1/",
                    "title": "Application Support Engineer",
                    "company": "Example SaaS Ltd",
                    "location": "Remote, Spain",
                    "description": "Support production applications, triage SQL errors, investigate API logs, document incidents, and coordinate escalations with engineering.",
                    "identity_verified": True,
                    "verification_reason": "LinkedIn job detail matched the selected card title, company, and source job id.",
                }
            ],
            "pages": [
                {
                    "page_number": 1,
                    "visible_job_ids": ["linkedin-job-1"],
                    "next_control_present": False,
                    "next_control_enabled": False,
                }
            ],
        },
    )

    assert captured.status_code == 200
    capture_payload = captured.json()
    assert capture_payload["source"] == "linkedin"
    assert capture_payload["mode"] == "supervised_live"
    assert capture_payload["verified_items"] == 1
    assert capture_payload["items"][0]["posting_id"]
    assert capture_payload["items"][0]["source_document_id"]

    refreshed = client.post("/api/evaluations/refresh")
    assert refreshed.status_code == 200

    inbox = client.get("/api/opportunity-index")
    assert inbox.status_code == 200
    items = inbox.json()
    assert len(items) == 1
    assert items[0]["posting_id"] == capture_payload["items"][0]["posting_id"]
    assert items[0]["title"] == "Application Support Engineer"
    assert items[0]["company"] == "Example SaaS Ltd"

    market = client.get("/api/market-intelligence")
    assert market.status_code == 200
    assert market.json()["total_active_records"] == 1


def test_linkedin_presence_capture_routes_to_command_center_not_review_inbox(tmp_path: Path) -> None:
    client = _client(tmp_path)

    captured = client.post(
        "/api/linkedin-command-center/captures",
        json={
            "category": "profile",
            "title": "Profile baseline",
            "source_url": "https://www.linkedin.com/in/example/",
            "visible_text": "IT Operations & Application Support Engineer profile evidence.",
            "notes": "User-approved profile snapshot.",
        },
    )

    assert captured.status_code == 200

    dashboard = client.get("/api/linkedin-command-center")
    assert dashboard.status_code == 200
    assert dashboard.json()["capture_count"] == 1

    inbox = client.get("/api/opportunity-index")
    assert inbox.status_code == 200
    assert inbox.json() == []

    market = client.get("/api/market-intelligence")
    assert market.status_code == 200
    assert market.json()["total_active_records"] == 0


def test_unverified_linkedin_job_capture_records_noise_without_posting(tmp_path: Path) -> None:
    client = _client(tmp_path)

    captured = client.post(
        "/api/captures/linkedin/live",
        json={
            "search_url": "https://www.linkedin.com/jobs/search/?keywords=dispatch",
            "requested_item_limit": 1,
            "items": [
                {
                    "source_job_id": "linkedin-noise-1",
                    "source_url": "https://www.linkedin.com/jobs/view/linkedin-noise-1/",
                    "title": "Dispatch Coordinator",
                    "company": "Noisy Recruiter",
                    "location": "Remote",
                    "description": "",
                    "identity_verified": False,
                    "verification_reason": "Detail panel did not verify the selected job identity.",
                }
            ],
            "pages": [
                {
                    "page_number": 1,
                    "visible_job_ids": ["linkedin-noise-1"],
                    "next_control_present": False,
                    "next_control_enabled": False,
                }
            ],
            "stop_reason": "submitted_batch_completed",
        },
    )

    assert captured.status_code == 200
    payload = captured.json()
    assert payload["verified_items"] == 0
    assert payload["rejected_items"] == 1
    assert payload["items"][0]["detail_status"] == "rejected_unverified"
    assert payload["items"][0]["posting_id"] is None

    inbox = client.get("/api/opportunity-index")
    assert inbox.status_code == 200
    assert inbox.json() == []
