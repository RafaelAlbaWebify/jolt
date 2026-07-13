from fastapi.testclient import TestClient

from jolt.main import create_app


def test_readiness_refresh_preserves_history(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'readiness-refresh.db').as_posix()}"
    client = TestClient(create_app(database_url))

    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/jobs/support",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Own production incidents, inspect logs, and troubleshoot SQL integrations."
            ),
        },
    )
    assert intake.status_code == 200
    posting_id = intake.json()["posting_id"]

    opportunities = client.get("/api/opportunities")
    assert opportunities.status_code == 200
    original_report_id = opportunities.json()[0]["readiness"]["report_id"]

    refreshed = client.post(f"/api/opportunities/{posting_id}/readiness/refresh")
    assert refreshed.status_code == 200
    refreshed_payload = refreshed.json()
    assert refreshed_payload["report_id"] != original_report_id
    assert refreshed_payload["supersedes_report_id"] == original_report_id
    assert refreshed_payload["refresh_reason"] == "manual_recalculation"
    assert refreshed_payload["is_current"] is True

    history = client.get(f"/api/opportunities/{posting_id}/readiness/history")
    assert history.status_code == 200
    reports = history.json()
    assert len(reports) == 2
    assert reports[0]["report_id"] == refreshed_payload["report_id"]
    assert reports[0]["is_current"] is True
    assert reports[1]["report_id"] == original_report_id
    assert reports[1]["is_current"] is False


def test_readiness_refresh_rejects_unknown_posting(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'missing.db').as_posix()}"
    client = TestClient(create_app(database_url))

    assert client.post("/api/opportunities/missing/readiness/refresh").status_code == 404
    assert client.get("/api/opportunities/missing/readiness/history").status_code == 404
