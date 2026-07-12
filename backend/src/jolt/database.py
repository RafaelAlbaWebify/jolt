from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


class Base(DeclarativeBase):
    pass


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProfileVersion(Base):
    __tablename__ = "profile_versions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    configuration_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Posting(Base):
    __tablename__ = "postings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), unique=True)
    canonical_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    company: Mapped[str] = mapped_column(Text, default="", nullable=False)
    location: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    identity_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    source_document: Mapped[SourceDocument] = relationship()


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    posting_id: Mapped[str] = mapped_column(ForeignKey("postings.id"), index=True)
    profile_version_id: Mapped[str] = mapped_column(ForeignKey("profile_versions.id"))
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    ranking_score: Mapped[int] = mapped_column(nullable=False)
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    posting_id: Mapped[str] = mapped_column(ForeignKey("postings.id"), index=True)
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("evaluations.id"), index=True)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evaluation_overridden: Mapped[bool] = mapped_column(default=False, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def default_database_url() -> str:
    configured = os.getenv("JOLT_DATABASE_URL")
    if configured:
        return configured
    data_dir = Path.cwd() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(data_dir / 'jolt.db').as_posix()}"


def create_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    url = database_url or default_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def utc_now() -> datetime:
    return datetime.now(UTC)


def session_scope(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = factory()
    try:
        yield session
    finally:
        session.close()
