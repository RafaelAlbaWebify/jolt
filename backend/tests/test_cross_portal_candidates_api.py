"""Discovery duplicate suggestions never merge postings or discard source evidence."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from jolt.capture_ingestion import ingest_capture_item
from jolt.database import Posting, PostingSourceIdentity, create_session_factory
from jolt.main import create_app
from jolt.schemas import ManualIntakeRequest
from jolt.sources.normalized_offer import NormalizedJobOffer
from jolt.sources.source_identity_registry import register_source_identity


DESCRIPTION = (
    "Support enterprise business applications and troubleshoot incidents. "
    "Investigate logs, coordinate fixes with engineers and document resolutions. "
) * 4


def test_cross_portal_candidates_are_read_only_and_conservative(tmp_path) -> None:
    url = f"sqlite:///{(tmp_path / 'candidates.db').as_posix()}"
    client = TestClient(create_app(url))
    factory = create_session_factory(url)
    with factory() as session:
        for portal, job_id, address, location in [
            ("linkedin", "li-12", "https://www.linkedin.com/jobs/view/li-12", "Madrid"),
            ("infojobs", "ij-34", "https://www.infojobs.net/job/ij-34", "Madrid"),
            ("indeed", "in-56", "https://es.indeed.com/viewjob?jk=in-56", "Barcelona"),
        ]:
            intake = ingest_capture_item(
                session,
                ManualIntakeRequest(
                    raw_text=(
                        f"Application Support Engineer\nExample Ltd\n"
                        f"Location: {location}\n{DESCRIPTION}"
                    ),
                    source_url=address,
                    source_type=f"{portal}_live",
                ),
            )
            register_source_identity(
                session,
                posting_id=intake.posting_id,
                source_document_id=intake.source_document_id,
                offer=NormalizedJobOffer(
                    portal=portal,
                    source_job_id=job_id,
                    source_url=address,
                    title="Application Support Engineer",
                    company="Example Ltd",
                    location=location,
                    description=DESCRIPTION,
                    identity_verified=True,
                    detail_verified=True,
                ),
            )
        session.commit()
        before = session.scalar(select(func.count()).select_from(Posting))

    response = client.get("/api/discovery-duplicate-candidates")
    assert response.status_code == 200
    candidates = response.json()
    assert len(candidates) == 3
    assert sum(item["decision"] == "probable_same_vacancy" for item in candidates) == 1
    assert sum(item["decision"] == "needs_review" for item in candidates) == 2
    assert all(item["first_posting_id"] != item["second_posting_id"] for item in candidates)
    assert client.get("/api/discovery-duplicate-candidates?limit=0").status_code == 422

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Posting)) == before
        assert session.scalar(select(func.count()).select_from(PostingSourceIdentity)) == 3


def test_cross_portal_candidates_empty_before_capture(tmp_path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"))
    response = client.get("/api/discovery-duplicate-candidates")
    assert response.status_code == 200
    assert response.json() == []
