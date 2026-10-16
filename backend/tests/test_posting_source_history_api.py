"""Per-posting provenance API returns bounded receipts without altering source data."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from jolt.database import PortalSourceObservation, PostingSourceIdentity, create_session_factory
from jolt.live_capture_workflow import run_linkedin_live_capture
from jolt.main import create_app
from jolt.schemas import LinkedInLiveCaptureItemRequest, LinkedInLiveCaptureRequest


def test_source_history_preserves_repeated_observations_and_source_identity(tmp_path) -> None:
    url = f"sqlite:///{(tmp_path / 'history.db').as_posix()}"
    client = TestClient(create_app(url))
    factory = create_session_factory(url)
    capture = LinkedInLiveCaptureRequest(
        search_url="https://www.linkedin.com/jobs/search/",
        items=[
            LinkedInLiveCaptureItemRequest(
                source_job_id="9988",
                source_url="https://www.linkedin.com/jobs/view/9988",
                title="Systems Support Engineer",
                company="Example Ltd",
                location="Madrid",
                description="Maintain infrastructure, diagnose application incidents, coordinate engineering.",
                identity_verified=True,
            )
        ],
    )
    with factory() as session:
        first = run_linkedin_live_capture(session, capture)
        second = run_linkedin_live_capture(session, capture)
        posting_id = first.items[0].posting_id
        assert posting_id == second.items[0].posting_id
        original_count = session.scalar(select(func.count()).select_from(PortalSourceObservation))
        assert original_count == 2

    response = client.get(f"/api/discovery-postings/{posting_id}/source-history")
    assert response.status_code == 200
    data = response.json()
    assert data["posting_id"] == posting_id
    assert len(data["sources"]) == 1
    assert data["sources"][0]["source_job_id"] == "9988"
    assert data["sources"][0]["first_seen_at"] <= data["sources"][0]["last_seen_at"]
    assert data["total_observations"] == 2
    assert data["truncated"] is False
    assert len(data["observations"]) == 2
    assert len({item["capture_item_id"] for item in data["observations"]}) == 2
    assert all(len(item["artifact_sha256"]) == 64 for item in data["observations"])
    assert "raw_payload" not in str(data)
    assert "description" not in str(data)

    bounded = client.get(f"/api/discovery-postings/{posting_id}/source-history?limit=1")
    assert bounded.status_code == 200
    assert bounded.json()["truncated"] is True
    assert bounded.json()["total_observations"] == 2
    assert len(bounded.json()["observations"]) == 1
    assert (
        client.get(f"/api/discovery-postings/{posting_id}/source-history?limit=0").status_code
        == 422
    )
    assert (
        client.get(f"/api/discovery-postings/{posting_id}/source-history?limit=501").status_code
        == 422
    )
    assert client.get("/api/discovery-postings/missing/source-history").status_code == 404

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(PortalSourceObservation)) == 2
        assert session.scalar(select(func.count()).select_from(PostingSourceIdentity)) == 1
