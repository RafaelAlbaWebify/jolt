from __future__ import annotations

from datetime import UTC, datetime

from jolt.database import Application, Posting, SourceDocument, create_session_factory
from jolt.opportunity_index import list_opportunity_index


def test_application_index_keeps_application_without_legacy_evaluation(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'application-index.db').as_posix()}"
    factory = create_session_factory(database_url)
    now = datetime.now(UTC)

    with factory() as session:
        source = SourceDocument(
            id="source-app-no-evaluation",
            source_type="manual",
            source_url="https://example.test/jobs/application-support",
            raw_text="Application Support Engineer\nExample Systems\nRemote Spain",
            content_hash="a" * 64,
            captured_at=now,
        )
        session.add(source)
        session.flush()

        posting = Posting(
            id="posting-app-no-evaluation",
            source_document_id=source.id,
            canonical_url=source.source_url,
            identity_key="manual:application-support",
            title="Application Support Engineer",
            company="Example Systems",
            location="Remote Spain",
            description=source.raw_text,
            identity_status="verified",
            created_at=now,
        )
        session.add(posting)
        session.flush()

        application = Application(
            id="application-no-evaluation",
            posting_id=posting.id,
            status="preparing",
            application_url="",
            resume_used="",
            notes="Created from a reviewed opportunity.",
            created_at=now,
            updated_at=now,
        )
        session.add(application)
        session.commit()

        result = list_opportunity_index(session, include_applied=True)

        assert len(result) == 1
        item = result[0]
        assert item.posting_id == posting.id
        assert item.application_id == application.id
        assert item.application_status == "preparing"
        assert item.evaluation_id is None
        assert item.recommendation == ""
        assert item.confidence == ""
        assert item.ranking_score == 0


def test_pending_opportunity_index_still_requires_legacy_evaluation(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'pending-index.db').as_posix()}"
    factory = create_session_factory(database_url)
    now = datetime.now(UTC)

    with factory() as session:
        source = SourceDocument(
            id="source-pending-no-evaluation",
            source_type="manual",
            source_url="https://example.test/jobs/pending",
            raw_text="Pending Support Engineer",
            content_hash="b" * 64,
            captured_at=now,
        )
        session.add(source)
        session.flush()
        session.add(
            Posting(
                id="posting-pending-no-evaluation",
                source_document_id=source.id,
                canonical_url=source.source_url,
                identity_key="manual:pending",
                title="Pending Support Engineer",
                company="Example Systems",
                location="Remote Spain",
                description=source.raw_text,
                identity_status="verified",
                created_at=now,
            )
        )
        session.commit()

        assert list_opportunity_index(session) == []
