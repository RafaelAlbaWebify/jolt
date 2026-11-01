import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(database_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))


def test_manual_intake_review_duplicate_and_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "jolt.db"
    client = _client(database_path)
    payload = {
        "source_url": "https://example.com/jobs/123?utm_source=test",
        "raw_text": (
            "Application Support Engineer\n"
            "Example Systems\n"
            "Location: Remote Spain\n"
            "Provide application support, SQL troubleshooting, incident ownership, "
            "and API analysis."
        ),
    }

    intake = client.post("/api/intake/manual", json=payload)
    assert intake.status_code == 200
    result = intake.json()
    assert result["identity_status"] == "new"
    assert result["title"] == "Application Support Engineer"
    assert result["company"] == "Example Systems"
    assert result["location"] == "Remote Spain"
    assert result["recommendation"] == "pursue"
    assert result["profile_version_id"] == "default-job-search:v1"
    assert result["engine_version"] == "rules-v1"

    ai_package = client.get("/api/ai-work-package/export")
    assert ai_package.status_code == 200
    review_inbox = ai_package.json()["review_inbox"]
    assert review_inbox["pack_type"] == "jolt_ai_review_bundle_input"
    assert review_inbox["counts"]["capture_items"] == 1
    assert review_inbox["jobs"][0]["posting_id"] == result["posting_id"]
    assert review_inbox["review_groups"][0]["capture"]["source"] == "manual"

    review = client.post(
        f"/api/opportunities/{result['posting_id']}/reviews",
        json={
            "evaluation_id": result["evaluation_id"],
            "decision": "pursue",
            "reason_code": "strong_alignment",
            "notes": "Prepare a tailored application.",
        },
    )
    assert review.status_code == 200
    assert review.json()["evaluation_overridden"] is False

    duplicate = client.post("/api/intake/manual", json=payload)
    assert duplicate.status_code == 200
    assert duplicate.json()["identity_status"] == "confirmed_duplicate"
    assert duplicate.json()["posting_id"] == result["posting_id"]
    assert duplicate.json()["source_document_id"] != result["source_document_id"]

    restarted_client = _client(database_path)
    refresh = restarted_client.post("/api/evaluations/refresh")
    assert refresh.status_code == 200
    assert refresh.json()["authoritative_engine"] == "profile-rules-v2"

    opportunities = restarted_client.get("/api/opportunities")
    assert opportunities.status_code == 200
    items = opportunities.json()
    assert len(items) == 1
    opportunity = items[0]
    assert opportunity["posting_id"] == result["posting_id"]
    assert opportunity["source_url"] == payload["source_url"]
    assert opportunity["recommendation"] == "pursue"
    assert opportunity["proposed_decision"] == "pursue"
    assert opportunity["confidence"] in {"medium", "high"}
    assert opportunity["ranking_score"] >= 50
    assert opportunity["profile_version_id"] == "rafael-job-search:v2"
    assert opportunity["engine_version"] == "profile-rules-v2"
    assert opportunity["review_decision"] == "pursue"
    assert opportunity["strengths"]
    assert opportunity["application_id"]
    assert opportunity["application_status"] == "preparing"


def test_missing_information_does_not_become_hard_reject(tmp_path: Path) -> None:
    client = _client(tmp_path / "uncertain.db")
    response = client.post(
        "/api/intake/manual",
        json={"raw_text": "Support Engineer\nUnknown Company\nGeneral troubleshooting role."},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["recommendation"] == "consider"
    assert result["confidence"] in {"low", "medium"}
    assert result["identity_status"] == "new"


@pytest.mark.parametrize("source_type", ["manual", "linkedin_live", "indeed_live"])
@pytest.mark.parametrize("decision", ["pursue", "reject"])
def test_one_human_decision_leaves_other_capture_jobs_pending(
    tmp_path: Path, source_type: str, decision: str
) -> None:
    database_path = tmp_path / "human-decision.db"
    client = _client(database_path)
    ids = []
    for number in (1, 2):
        response = client.post(
            "/api/intake/manual",
            json={
                "source_url": f"https://example.com/jobs/human-{number}",
                "source_type": source_type,
                "raw_text": f"Support Engineer {number}\nExample Company\nGeneral support duties.",
            },
        )
        assert response.status_code == 200, response.text
        ids.append(response.json()["posting_id"])

    # Model two already-ingested postings in one source capture before the human acts.
    with sqlite3.connect(database_path) as connection:
        capture_id = connection.execute(
            "SELECT capture_run_id FROM capture_items WHERE posting_id = ?", (ids[0],)
        ).fetchone()[0]
        connection.execute(
            "UPDATE capture_items SET capture_run_id = ? WHERE posting_id = ?",
            (capture_id, ids[1]),
        )
        connection.execute(
            "UPDATE capture_runs SET source = ?, observed_item_count = 2, requested_item_limit = 2 "
            "WHERE id = ?",
            (source_type.split("_")[0], capture_id),
        )

    before = client.get("/api/ai-review/opportunity-index").json()
    assert {item["posting_id"] for item in before} == set(ids)
    assert all(item["ai_review_status"] == "awaiting_ai_review" for item in before)

    response = client.post(f"/api/opportunities/{ids[0]}/reviews", json={"decision": decision})
    assert response.status_code == 200, response.text
    assert response.json()["ai_review_id"] is None
    assert response.json()["evaluation_id"] is None
    assert response.json()["evaluation_overridden"] is False

    # Repeat actions must not create another application or application-created event.
    repeated = client.post(f"/api/opportunities/{ids[0]}/reviews", json={"decision": decision})
    assert repeated.status_code == 200, repeated.text
    restarted = _client(database_path)
    pending = restarted.get("/api/ai-review/opportunity-index").json()
    assert [item["posting_id"] for item in pending] == [ids[1]]
    assert pending[0]["ai_review_status"] == "awaiting_ai_review"
    exported = restarted.get("/api/ai-work-package/export")
    assert exported.status_code == 200, exported.text
    jobs = exported.json()["review_inbox"]["jobs"]
    assert {job["posting_id"] for job in jobs} == {ids[1]}

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ai_reviews").fetchone()[0] == 0
        records = connection.execute(
            "SELECT ai_review_id, evaluation_id, decision FROM review_decisions WHERE posting_id = ?",
            (ids[0],),
        ).fetchall()
        assert records == [(None, None, decision), (None, None, decision)]
        expected_applications = 1 if decision == "pursue" else 0
        assert (
            connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
            == expected_applications
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM application_events WHERE event_type = 'application_created'"
            ).fetchone()[0]
            == expected_applications
        )
