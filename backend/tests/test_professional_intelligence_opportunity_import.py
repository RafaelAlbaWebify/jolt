from __future__ import annotations

from sqlalchemy import func, select

from jolt.capture_ingestion import ingest_capture_item
from jolt.database import Posting, SourceDocument, create_session_factory
from jolt.professional_intelligence_opportunity_import import (
    _extract_candidates_from_text,
)


def test_professional_candidates_from_same_source_page_remain_distinct(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'professional-import.db').as_posix()}"
    factory = create_session_factory(database_url)

    source_url = "https://www.linkedin.com/jobs/search/?keywords=support"

    rendered_text = """
Support Engineer
Company Alpha
Remote Spain
Troubleshoot APIs and production incidents.

Cloud Engineer
Company Beta
Madrid
Azure cloud operations and automation.

Systems Administrator
Company Gamma
Vigo
Windows, Active Directory and infrastructure support.
"""

    candidates = _extract_candidates_from_text(
        source_id="linkedin-jobs",
        source_url=source_url,
        text=rendered_text,
    )

    assert len(candidates) == 3

    with factory() as session:
        results = [
            ingest_capture_item(
                session,
                candidate,
                use_source_url_for_identity=False,
            )
            for candidate in candidates
        ]
        session.commit()

    assert len({result.posting_id for result in results}) == 3
    assert all(result.identity_status == "new" for result in results)

    with factory() as session:
        postings = session.scalars(select(Posting).order_by(Posting.created_at)).all()

        source_documents = session.scalars(
            select(SourceDocument).order_by(SourceDocument.captured_at)
        ).all()

        posting_count = int(session.scalar(select(func.count()).select_from(Posting)) or 0)

    assert posting_count == 3
    assert [posting.title for posting in postings] == [
        "Support Engineer",
        "Cloud Engineer",
        "Systems Administrator",
    ]

    assert all(source.source_url == source_url for source in source_documents)


def test_professional_identical_candidate_evidence_still_deduplicates(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'professional-dedup.db').as_posix()}"
    factory = create_session_factory(database_url)

    source_url = "https://www.linkedin.com/jobs/search/?keywords=support"

    rendered_text = """
Support Engineer
Company Alpha
Remote Spain
Troubleshoot APIs and production incidents.
"""

    first = _extract_candidates_from_text(
        source_id="linkedin-jobs",
        source_url=source_url,
        text=rendered_text,
    )[0]

    second = _extract_candidates_from_text(
        source_id="linkedin-jobs",
        source_url=source_url,
        text=rendered_text,
    )[0]

    with factory() as session:
        first_result = ingest_capture_item(
            session,
            first,
            use_source_url_for_identity=False,
        )

        second_result = ingest_capture_item(
            session,
            second,
            use_source_url_for_identity=False,
        )

        session.commit()

    assert first_result.posting_id == second_result.posting_id
    assert second_result.identity_status == "confirmed_duplicate"


def test_professional_extractor_does_not_promote_role_prose_to_title() -> None:
    source_url = "https://www.linkedin.com/jobs/search/?keywords=support"

    rendered_text = """
Application Support Engineer
Acme SaaS Operations
Remote Spain
Troubleshoot SQL incidents, API integrations, logs, RCA, Microsoft 365 and Windows application support.

Technical Support Engineer
Contoso Cloud Services
Hybrid Galicia
Support enterprise users with Azure, DNS, PowerShell, ServiceNow and production incidents.
"""

    candidates = _extract_candidates_from_text(
        source_id="linkedin-jobs",
        source_url=source_url,
        text=rendered_text,
    )

    assert [candidate.raw_text.splitlines()[0] for candidate in candidates] == [
        "Application Support Engineer",
        "Technical Support Engineer",
    ]
