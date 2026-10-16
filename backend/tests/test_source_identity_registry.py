"""Source identity persistence protects Postings and their portal provenance."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from jolt.database import Base, Posting, PostingSourceIdentity, SourceDocument
from jolt.sources.normalized_offer import NormalizedJobOffer
from jolt.sources.source_identity_registry import (
    list_posting_sources,
    register_source_identity,
)


def _posting(session: Session, identifier: str) -> str:
    document = SourceDocument(
        id="doc-" + identifier,
        source_type="manual",
        source_url="",
        raw_text="Support engineer",
        content_hash="hash-" + identifier,
        captured_at=datetime.now(UTC),
    )
    session.add(document)
    posting = Posting(
        id=identifier,
        source_document_id=document.id,
        canonical_url="",
        identity_key="identity-" + identifier,
        title="Support engineer",
        company="Example",
        location="Madrid",
        description="Support business applications",
        identity_status="new",
        created_at=datetime.now(UTC),
    )
    session.add(posting)
    session.flush()
    return posting.id


def _offer(portal: str, identifier: str, verified: bool = True) -> NormalizedJobOffer:
    hosts = {"linkedin": "www.linkedin.com", "infojobs": "www.infojobs.net"}
    return NormalizedJobOffer(
        portal=portal,
        source_job_id=identifier,
        source_url=f"https://{hosts[portal]}/jobs/{identifier}",
        title="Support engineer",
        company="Example",
        location="Madrid",
        description="Support business applications",
        identity_verified=verified,
        detail_verified=verified,
    )


def test_multiple_portals_can_point_at_one_posting_without_deleting_evidence(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'source.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        posting_id = _posting(session, "p1")
        one = register_source_identity(
            session, posting_id=posting_id, offer=_offer("linkedin", "123")
        )
        repeated = register_source_identity(
            session, posting_id=posting_id, offer=_offer("linkedin", "123")
        )
        assert repeated.id == one.id
        assert repeated.first_seen_at <= repeated.last_seen_at
        register_source_identity(
            session, posting_id=posting_id, offer=_offer("infojobs", "abc")
        )
        assert [item.portal for item in list_posting_sources(session, posting_id)] == [
            "infojobs",
            "linkedin",
        ]
        assert len(session.scalars(select(Posting)).all()) == 1
        session.commit()
    with Session(engine) as session:
        assert len(session.scalars(select(PostingSourceIdentity)).all()) == 2


def test_identity_cannot_silently_move_between_postings(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'source.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        first = _posting(session, "one")
        second = _posting(session, "two")
        register_source_identity(session, posting_id=first, offer=_offer("linkedin", "123"))
        with pytest.raises(ValueError, match="already linked"):
            register_source_identity(
                session, posting_id=second, offer=_offer("linkedin", "123")
            )
        assert len(session.scalars(select(Posting)).all()) == 2


def test_unverified_identity_is_not_registered(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'source.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        posting_id = _posting(session, "one")
        with pytest.raises(ValueError, match="Unverified"):
            register_source_identity(
                session, posting_id=posting_id, offer=_offer("infojobs", "abc", False)
            )
        assert session.scalars(select(PostingSourceIdentity)).all() == []
