"""Verified live source identities are persisted without changing capture responses."""

from sqlalchemy import select

from jolt.database import PostingSourceIdentity, create_session_factory
from jolt.indeed_live_capture import run_indeed_live_capture
from jolt.live_capture_workflow import run_linkedin_live_capture
from jolt.schemas import (
    IndeedLiveCaptureItemRequest,
    IndeedLiveCaptureRequest,
    LinkedInLiveCaptureItemRequest,
    LinkedInLiveCaptureRequest,
)


def test_verified_linkedin_and_indeed_captures_register_source_ids(tmp_path) -> None:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'sources.db').as_posix()}")
    cases = [
        (
            run_linkedin_live_capture,
            LinkedInLiveCaptureRequest(
                search_url="https://www.linkedin.com/jobs/search/",
                items=[
                    LinkedInLiveCaptureItemRequest(
                        source_job_id="li-1",
                        source_url="https://www.linkedin.com/jobs/view/li-1",
                        title="IT Support Engineer",
                        company="Example One",
                        location="Madrid",
                        description="Maintain business applications and troubleshoot incidents.",
                        identity_verified=True,
                    )
                ],
            ),
            "linkedin",
            "li-1",
        ),
        (
            run_indeed_live_capture,
            IndeedLiveCaptureRequest(
                search_url="https://es.indeed.com/jobs?q=support",
                items=[
                    IndeedLiveCaptureItemRequest(
                        source_job_id="in-1",
                        source_url="https://es.indeed.com/viewjob?jk=in-1",
                        title="Application Support",
                        company="Example Two",
                        location="Vigo",
                        description="Diagnose integrations and maintain IT services.",
                        identity_verified=True,
                    )
                ],
            ),
            "indeed",
            "in-1",
        ),
    ]
    with factory() as session:
        for capture, request, portal, identifier in cases:
            response = capture(session, request)
            assert response.verified_items == 1
            item = response.items[0]
            recorded = session.scalar(
                select(PostingSourceIdentity).where(
                    PostingSourceIdentity.portal == portal,
                    PostingSourceIdentity.source_job_id == identifier,
                )
            )
            assert recorded is not None
            assert recorded.posting_id == item.posting_id
            assert recorded.source_document_id == item.source_document_id

    with factory() as session:
        assert len(session.scalars(select(PostingSourceIdentity)).all()) == 2


def test_repeated_linkedin_capture_refreshes_identity_without_duplicate_link(tmp_path) -> None:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'repeat.db').as_posix()}")
    request = LinkedInLiveCaptureRequest(
        search_url="https://www.linkedin.com/jobs/search/",
        items=[
            LinkedInLiveCaptureItemRequest(
                source_job_id="12345",
                source_url="https://www.linkedin.com/jobs/view/12345",
                title="IT Support",
                company="Example",
                location="Vigo",
                description="Support internal systems and troubleshoot failures.",
                identity_verified=True,
            )
        ],
    )
    with factory() as session:
        first = run_linkedin_live_capture(session, request)
        second = run_linkedin_live_capture(session, request)
        assert first.items[0].posting_id == second.items[0].posting_id
        sources = session.scalars(select(PostingSourceIdentity)).all()
        assert len(sources) == 1
        assert sources[0].first_seen_at <= sources[0].last_seen_at
