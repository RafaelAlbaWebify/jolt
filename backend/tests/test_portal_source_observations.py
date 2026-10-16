"""Verified portal observations survive repeat captures and reject altered receipts."""

import pytest
from sqlalchemy import func, select

from jolt.database import PortalSourceObservation, create_session_factory
from jolt.live_capture_workflow import run_linkedin_live_capture
from jolt.schemas import LinkedInLiveCaptureItemRequest, LinkedInLiveCaptureRequest
from jolt.sources.portal_observations import (
    list_portal_observations,
    record_portal_observation,
)


def _request(*, verified: bool = True) -> LinkedInLiveCaptureRequest:
    return LinkedInLiveCaptureRequest(
        search_url="https://www.linkedin.com/jobs/search/",
        items=[
            LinkedInLiveCaptureItemRequest(
                source_job_id="12345",
                source_url="https://www.linkedin.com/jobs/view/12345",
                title="Application Support Engineer",
                company="Example",
                location="Madrid",
                description="Support production systems and diagnose application errors.",
                identity_verified=verified,
            )
        ],
    )


def test_two_verified_captures_create_two_independent_source_receipts(tmp_path) -> None:
    url = f"sqlite:///{(tmp_path / 'observations.db').as_posix()}"
    factory = create_session_factory(url)
    with factory() as session:
        first = run_linkedin_live_capture(session, _request())
        second = run_linkedin_live_capture(session, _request())
        assert first.items[0].posting_id == second.items[0].posting_id
        posting_id = first.items[0].posting_id
        assert posting_id is not None
        rows = list_portal_observations(session, posting_id)
        assert len(rows) == 2
        assert rows[0].capture_run_id != rows[1].capture_run_id
        assert rows[0].capture_item_id != rows[1].capture_item_id
        assert rows[0].artifact_sha256 == rows[1].artifact_sha256
        assert all(len(row.artifact_sha256) == 64 for row in rows)
        before = rows[0]
        repeated = record_portal_observation(
            session, capture_item_id=before.capture_item_id, artifact_sha256=before.artifact_sha256
        )
        assert repeated.id == before.id
        with pytest.raises(ValueError, match="hash mismatch|cannot be rewritten"):
            record_portal_observation(
                session, capture_item_id=before.capture_item_id, artifact_sha256="0" * 64
            )
        assert session.scalar(select(func.count()).select_from(PortalSourceObservation)) == 2


def test_unverified_capture_never_creates_portal_receipt(tmp_path) -> None:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'unverified.db').as_posix()}")
    with factory() as session:
        captured = run_linkedin_live_capture(session, _request(verified=False))
        assert captured.verified_items == 0
        assert session.scalars(select(PortalSourceObservation)).all() == []
        with pytest.raises(ValueError, match="verified"):
            record_portal_observation(
                session, capture_item_id=captured.items[0].capture_item_id,
                artifact_sha256="a" * 64,
            )
