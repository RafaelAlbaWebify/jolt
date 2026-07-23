from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_application_lifecycle_from_intake_to_accepted_offer(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt-lifecycle.db').as_posix()}"
    client = TestClient(create_app(database_url))

    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://jobs.example.com/application-support-engineer",
            "source_type": "manual_test",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Own production incidents, troubleshoot SQL-backed applications, "
                "support APIs and integrations, and improve support automation."
            ),
        },
    )
    assert intake.status_code == 200
    opportunity = intake.json()
    posting_id = opportunity["posting_id"]
    evaluation_id = opportunity["evaluation_id"]

    blocked_application = client.post(
        f"/api/opportunities/{posting_id}/applications",
        json={"application_url": "https://jobs.example.com/application-support-engineer/apply"},
    )
    assert blocked_application.status_code == 409
    assert "pursue decision" in blocked_application.json()["detail"]

    review = client.post(
        f"/api/opportunities/{posting_id}/reviews",
        json={
            "evaluation_id": evaluation_id,
            "decision": "pursue",
            "reason_code": "strong_evidence_match",
            "notes": "Human review confirmed the role is suitable.",
        },
    )
    assert review.status_code == 200
    assert review.json()["decision"] == "pursue"

    created = client.post(
        f"/api/opportunities/{posting_id}/applications",
        json={
            "application_url": "https://jobs.example.com/application-support-engineer/apply",
            "resume_used": "Rafael_Alba_Application_Support_CV.pdf",
            "notes": "Preparation started after human approval.",
        },
    )
    assert created.status_code == 200
    application = created.json()
    application_id = application["application_id"]
    assert application["status"] == "preparing"
    assert application["outcome_type"] is None
    assert [event["to_status"] for event in application["events"]] == ["preparing"]

    transitions = [
        ("submitted", "Application submitted manually."),
        ("acknowledged", "Employer acknowledgement received."),
        ("recruiter_screen", "Recruiter screen completed."),
        ("technical_interview", "Technical interview completed."),
        ("hiring_manager_interview", "Hiring manager interview completed."),
        ("final_interview", "Final interview completed."),
        ("offer", "Written offer received."),
    ]

    expected_statuses = ["preparing"]
    for status, notes in transitions:
        response = client.post(
            f"/api/applications/{application_id}/transitions",
            json={"status": status, "notes": notes},
        )
        assert response.status_code == 200
        application = response.json()
        expected_statuses.append(status)
        assert application["status"] == status
        assert [event["to_status"] for event in application["events"]] == expected_statuses

    backward_transition = client.post(
        f"/api/applications/{application_id}/transitions",
        json={"status": "submitted", "notes": "Corrected an incorrectly recorded stage."},
    )
    assert backward_transition.status_code == 200
    backward_application = backward_transition.json()
    assert backward_application["status"] == "submitted"
    assert backward_application["events"][-1]["from_status"] == "offer"
    assert backward_application["events"][-1]["to_status"] == "submitted"
    assert backward_application["events"][-1]["notes"] == "Corrected an incorrectly recorded stage."

    restored_offer = client.post(
        f"/api/applications/{application_id}/transitions",
        json={"status": "offer", "notes": "Restored the verified current stage."},
    )
    assert restored_offer.status_code == 200
    assert restored_offer.json()["status"] == "offer"

    outcome = client.post(
        f"/api/applications/{application_id}/outcomes",
        json={
            "outcome_type": "offer_accepted",
            "reason_code": "accepted_suitable_offer",
            "notes": "Offer accepted manually by the user.",
        },
    )
    assert outcome.status_code == 200
    completed = outcome.json()
    assert completed["status"] == "closed"
    assert completed["outcome_type"] == "offer_accepted"
    assert completed["events"][-1]["event_type"] == "outcome_recorded"
    assert completed["events"][-1]["from_status"] == "offer"
    assert completed["events"][-1]["to_status"] == "closed"

    duplicate_outcome = client.post(
        f"/api/applications/{application_id}/outcomes",
        json={"outcome_type": "offer_accepted"},
    )
    assert duplicate_outcome.status_code == 409
    assert "already has an outcome" in duplicate_outcome.json()["detail"]

    stored_application = client.get(f"/api/applications/{application_id}")
    assert stored_application.status_code == 200
    assert stored_application.json() == completed

    workbench = client.get("/api/opportunities")
    assert workbench.status_code == 200
    workbench_item = next(item for item in workbench.json() if item["posting_id"] == posting_id)
    assert workbench_item["review_decision"] == "pursue"
    assert workbench_item["application_id"] == application_id
    assert workbench_item["application_status"] == "closed"
    assert workbench_item["outcome_type"] == "offer_accepted"
