from __future__ import annotations

import hashlib
import json

from sqlalchemy import select

from jolt.capture_artifacts import CaptureArtifact
from jolt.database import CaptureItem, create_session_factory
from jolt.live_capture_workflow import run_linkedin_live_capture
from jolt.schemas import LinkedInLiveCaptureItemRequest, LinkedInLiveCaptureRequest


def test_live_capture_preserves_raw_artifact_and_hash(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'capture-artifact.db').as_posix()}"
    factory = create_session_factory(database_url)
    session = factory()
    try:
        evidence = LinkedInLiveCaptureItemRequest(
            source_job_id="12345",
            source_url="https://www.linkedin.com/jobs/view/12345",
            title="Application Support Engineer",
            company="Example Company",
            location="Spain",
            description="Support production applications, SQL, APIs, incidents, and integrations.",
            identity_verified=True,
            verification_reason="Detail title and source job id matched.",
        )
        response = run_linkedin_live_capture(
            session,
            LinkedInLiveCaptureRequest(
                search_url="https://www.linkedin.com/jobs/search/",
                items=[evidence],
            ),
        )

        item = session.scalar(select(CaptureItem))
        artifact = session.scalar(select(CaptureArtifact))
        assert item is not None
        assert artifact is not None
        assert artifact.capture_item_id == item.id
        assert artifact.artifact_type == "linkedin_live_item_json"
        assert artifact.content_type == "application/json"

        expected_payload = json.dumps(evidence.model_dump(mode="json"), sort_keys=True)
        expected_hash = hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()
        assert artifact.raw_payload == expected_payload
        assert artifact.content_hash == expected_hash
        assert response.items[0].artifact_id == artifact.id
        assert response.items[0].artifact_hash == expected_hash

        stored = response.model_dump(mode="json")
        assert "raw_payload" not in json.dumps(stored)
    finally:
        session.close()
