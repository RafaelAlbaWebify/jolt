from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from jolt.capture_ingestion import ingest_capture_item
from jolt.database import Posting, SourceDocument, create_session_factory
from jolt.identity_evidence import opportunity_identity_evidence
from jolt.schemas import ManualIntakeRequest


def test_duplicate_capture_keeps_first_source_as_original_provenance(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'capture-provenance.db').as_posix()}"
    factory = create_session_factory(database_url)

    source_url = "https://www.linkedin.com/jobs/view/9876543210"

    first_text = (
        "Application Support Engineer\n"
        "Example Systems\n"
        "Location: Spain\n"
        "Initial captured application-support evidence."
    )
    refreshed_text = (
        "Application Support Engineer\n"
        "Example Systems\n"
        "Location: Remote Spain\n"
        "Refreshed application-support, SQL, API and incident evidence."
    )

    with factory() as session:
        first = ingest_capture_item(
            session,
            ManualIntakeRequest(
                source_type="linkedin_live",
                source_url=source_url,
                raw_text=first_text,
            ),
        )
        session.commit()

        first_source_id = first.source_document_id
        posting_id = first.posting_id

    with factory() as session:
        second = ingest_capture_item(
            session,
            ManualIntakeRequest(
                source_type="linkedin_live",
                source_url=source_url + "?trk=duplicate",
                raw_text=refreshed_text,
            ),
        )
        session.commit()

        posting = session.get(Posting, posting_id)
        assert posting is not None
        assert second.identity_status == "confirmed_duplicate"
        assert posting.source_document_id == first_source_id
        assert posting.description == refreshed_text

        evidence = opportunity_identity_evidence(session, posting_id)

        assert [item["source_document_id"] for item in evidence["evidence"]] == [
            first_source_id,
            second.source_document_id,
        ]
        assert [item["identity_status"] for item in evidence["evidence"]] == [
            "original",
            "confirmed_duplicate",
        ]


def test_identity_evidence_repairs_historical_latest_source_pointer_without_db_backfill(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'historical-provenance.db').as_posix()}"
    factory = create_session_factory(database_url)

    source_url = "https://www.linkedin.com/jobs/view/1122334455"
    raw_text = (
        "Systems Engineer\n"
        "Example Infrastructure\n"
        "Location: Remote Spain\n"
        "Windows, systems operations and incident response."
    )

    with factory() as session:
        first = ingest_capture_item(
            session,
            ManualIntakeRequest(
                source_type="linkedin_live",
                source_url=source_url,
                raw_text=raw_text,
            ),
        )
        session.commit()

        first_source_id = first.source_document_id
        posting_id = first.posting_id

    with factory() as session:
        second = ingest_capture_item(
            session,
            ManualIntakeRequest(
                source_type="linkedin_live",
                source_url=source_url + "?trk=duplicate",
                raw_text=raw_text,
            ),
        )
        session.commit()

        first_source = session.get(SourceDocument, first_source_id)
        second_source = session.get(SourceDocument, second.source_document_id)
        posting = session.get(Posting, posting_id)

        assert first_source is not None
        assert second_source is not None
        assert posting is not None

        second_source.captured_at = first_source.captured_at + timedelta(seconds=1)

        # Simulate a historical row written by the old implementation,
        # which moved source_document_id to the newest duplicate.
        posting.source_document_id = second.source_document_id
        session.commit()

    with factory() as session:
        evidence = opportunity_identity_evidence(session, posting_id)

        assert [item["source_document_id"] for item in evidence["evidence"]] == [
            first_source_id,
            second.source_document_id,
        ]
        assert [item["identity_status"] for item in evidence["evidence"]] == [
            "original",
            "confirmed_duplicate",
        ]

        # Read-time repair must not mutate the historical database row.
        stored_pointer = session.scalar(
            select(Posting.source_document_id).where(Posting.id == posting_id)
        )
        assert stored_pointer == second.source_document_id
