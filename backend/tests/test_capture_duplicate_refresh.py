from __future__ import annotations

from sqlalchemy import func, select

from jolt.capture_ingestion import ingest_capture_item
from jolt.database import Evaluation, Posting, SourceDocument, create_session_factory
from jolt.schemas import ManualIntakeRequest


def test_duplicate_capture_refreshes_posting_with_newest_evidence(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'duplicate-refresh.db').as_posix()}"
    factory = create_session_factory(database_url)

    source_url = "https://www.linkedin.com/jobs/view/1234567890"

    polluted = (
        "Technical Support Engineer\n"
        "Example Company\n"
        "Location: Spain\n"
        "Provide technical support and incident ownership.\n"
        "Job search faster with Premium\n"
        "Portuguese required relocation mandatory management role."
    )

    clean = (
        "Technical Support Engineer\n"
        "Example Company\n"
        "Location: Remote Spain\n"
        "Provide technical support, incident ownership, Windows troubleshooting, "
        "and customer documentation."
    )

    with factory() as session:
        first = ingest_capture_item(
            session,
            ManualIntakeRequest(
                source_type="linkedin_live",
                source_url=source_url,
                raw_text=polluted,
            ),
        )
        session.commit()

        first_posting_id = first.posting_id
        first_source_id = first.source_document_id
        first_evaluation_id = first.evaluation_id

    with factory() as session:
        second = ingest_capture_item(
            session,
            ManualIntakeRequest(
                source_type="linkedin_live",
                source_url=source_url + "?trk=duplicate",
                raw_text=clean,
            ),
        )
        session.commit()

        posting = session.get(Posting, first_posting_id)

        assert posting is not None
        assert second.identity_status == "confirmed_duplicate"
        assert second.posting_id == first_posting_id
        assert second.source_document_id != first_source_id
        assert second.evaluation_id != first_evaluation_id

        assert posting.source_document_id == second.source_document_id
        assert posting.title == "Technical Support Engineer"
        assert posting.company == "Example Company"
        assert posting.location == "Remote Spain"
        assert posting.description == clean

        assert "Job search faster with Premium" not in posting.description
        assert "Portuguese required" not in posting.description
        assert "relocation mandatory" not in posting.description

        source_count = session.scalar(select(func.count()).select_from(SourceDocument))
        posting_count = session.scalar(select(func.count()).select_from(Posting))
        evaluation_count = session.scalar(select(func.count()).select_from(Evaluation))

        assert source_count == 2
        assert posting_count == 1
        assert evaluation_count == 2

        source_ids = set(session.scalars(select(SourceDocument.id)).all())

        assert source_ids == {
            first_source_id,
            second.source_document_id,
        }
