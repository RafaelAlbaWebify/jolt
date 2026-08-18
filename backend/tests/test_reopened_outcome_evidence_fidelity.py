from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from jolt.database import ApplicationEvent, Outcome, create_session_factory
from jolt.main import create_app


def test_reopening_preserves_complete_historical_outcome(tmp_path: Path) -> None:
    database_path = tmp_path / "jolt.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    client = TestClient(create_app(database_url))

    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/jobs/outcome-history",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Support production applications, incidents and integrations."
            ),
        },
    )
    assert intake.status_code == 200

    intake_payload = intake.json()
    posting_id = intake_payload["posting_id"]
    evaluation_id = intake_payload["evaluation_id"]

    review = client.post(
        f"/api/opportunities/{posting_id}/reviews",
        json={
            "evaluation_id": evaluation_id,
            "decision": "pursue",
            "reason_code": "test_fixture",
            "notes": "Regression fixture pursue decision.",
        },
    )
    assert review.status_code == 200

    application_response = client.post(
        f"/api/opportunities/{posting_id}/applications",
        json={
            "application_url": "",
            "resume_used": "",
            "notes": "",
        },
    )
    assert application_response.status_code == 200
    application_id = application_response.json()["application_id"]

    transition = client.post(
        f"/api/applications/{application_id}/transitions",
        json={
            "status": "technical_interview",
            "notes": "",
        },
    )
    assert transition.status_code == 200

    outcome_response = client.post(
        f"/api/applications/{application_id}/outcomes",
        json={
            "outcome_type": "rejected_by_employer",
            "reason_code": "technical_depth",
            "notes": "Needed deeper product troubleshooting.",
        },
    )
    assert outcome_response.status_code == 200

    session_factory = create_session_factory(database_url)

    with session_factory() as session:
        original = session.scalar(select(Outcome).where(Outcome.application_id == application_id))
        assert original is not None

        expected = {
            "id": original.id,
            "posting_id": original.posting_id,
            "application_id": original.application_id,
            "outcome_type": original.outcome_type,
            "stage_reached": original.stage_reached,
            "reason_code": original.reason_code,
            "notes": original.notes,
            "recorded_at": original.recorded_at.isoformat(),
        }

    reopen = client.post(
        f"/api/applications/{application_id}/transitions",
        json={
            "status": "technical_interview",
            "notes": "Employer restarted the process.",
        },
    )
    assert reopen.status_code == 200

    with session_factory() as session:
        active_outcome = session.scalar(
            select(Outcome).where(Outcome.application_id == application_id)
        )
        assert active_outcome is None

        event = session.scalar(
            select(ApplicationEvent)
            .where(
                ApplicationEvent.application_id == application_id,
                ApplicationEvent.event_type == "application_reopened",
            )
            .order_by(ApplicationEvent.occurred_at.desc())
        )
        assert event is not None

        prefix = "Preserved outcome JSON: "
        assert prefix in event.notes

        preserved_json = event.notes.split(prefix, 1)[1]
        preserved = json.loads(preserved_json)

        assert preserved == expected
        assert preserved["stage_reached"] == "technical_interview"
        assert preserved["recorded_at"]
        datetime.fromisoformat(preserved["recorded_at"]).astimezone(UTC)
