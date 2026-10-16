"""Confirmation links equivalent postings without overwriting their existing records."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from jolt.capture_ingestion import ingest_capture_item
from jolt.database import (
    ConfirmedDuplicateLink,
    Posting,
    PostingSourceIdentity,
    create_session_factory,
)
from jolt.main import create_app
from jolt.schemas import ManualIntakeRequest
from jolt.sources.normalized_offer import NormalizedJobOffer
from jolt.sources.source_identity_registry import register_source_identity

DESCRIPTION = (
    "Support enterprise business applications and investigate production incidents. "
    "Coordinate with engineers, inspect logs, and document technical resolutions. "
) * 3


def test_confirmed_duplicates_preserve_both_postings_and_all_portal_sources(tmp_path) -> None:
    url = f"sqlite:///{(tmp_path / 'confirmed.db').as_posix()}"
    client = TestClient(create_app(url))
    factory = create_session_factory(url)
    posting_ids = []
    with factory() as session:
        for portal, job_id, address in [
            ("linkedin", "li-1", "https://www.linkedin.com/jobs/view/li-1"),
            ("infojobs", "ij-2", "https://www.infojobs.net/job/ij-2"),
        ]:
            intake = ingest_capture_item(
                session,
                ManualIntakeRequest(
                    raw_text=f"Application Support Engineer\nExample Ltd\nLocation: Madrid\n{DESCRIPTION}",
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
                    location="Madrid",
                    description=DESCRIPTION,
                    identity_verified=True,
                    detail_verified=True,
                ),
            )
            posting_ids.append(intake.posting_id)
        session.commit()

    first, second = posting_ids
    payload = {
        "first_posting_id": first,
        "second_posting_id": second,
        "confirmation": "CONFIRM SAME VACANCY",
    }
    assert len(client.get("/api/discovery-duplicate-candidates").json()) == 1
    rejected = client.post(
        "/api/discovery-confirm-duplicate",
        json={**payload, "confirmation": "yes"},
    )
    assert rejected.status_code == 422

    response = client.post("/api/discovery-confirm-duplicate", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"

    again = client.post("/api/discovery-confirm-duplicate", json=payload)
    assert again.status_code == 200
    assert again.json()["status"] == "already_confirmed"
    assert client.get("/api/discovery-duplicate-candidates").json() == []

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Posting)) == 2
        assert session.scalar(select(func.count()).select_from(PostingSourceIdentity)) == 2
        assert session.scalar(select(func.count()).select_from(ConfirmedDuplicateLink)) == 1


def test_invalid_or_self_confirmation_rejected(tmp_path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'invalid.db').as_posix()}"))
    response = client.post(
        "/api/discovery-confirm-duplicate",
        json={
            "first_posting_id": "same",
            "second_posting_id": "same",
            "confirmation": "CONFIRM SAME VACANCY",
        },
    )
    assert response.status_code == 422
