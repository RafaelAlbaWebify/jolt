from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import inspect

from jolt.database import Base, create_session_factory

HEAD_REVISION = "20260724_0010"


def test_session_factory_uses_alembic_without_create_all(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "runtime.db"
    database_url = f"sqlite:///{database_path.as_posix()}"

    def fail_create_all(*args, **kwargs) -> None:
        raise AssertionError("Base.metadata.create_all must not own runtime schema creation")

    monkeypatch.setattr(Base.metadata, "create_all", fail_create_all)

    factory = create_session_factory(database_url)
    engine = factory.kw["bind"]
    inspector = inspect(engine)

    assert inspector.has_table("source_documents")
    assert inspector.has_table("capture_runs")
    assert inspector.has_table("capture_artifacts")
    assert inspector.has_table("application_readiness_reports")
    assert inspector.has_table("application_contacts")
    assert inspector.has_table("application_documents")
    assert inspector.has_table("professional_source_overrides")
    assert inspector.has_table("professional_capture_runs")
    assert inspector.has_table("professional_capture_artifacts")
    assert inspector.has_table("alembic_version")

    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()

    assert revision == (HEAD_REVISION,)


def test_repeated_session_factory_creation_is_migration_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "repeated.db"
    database_url = f"sqlite:///{database_path.as_posix()}"

    first_factory = create_session_factory(database_url)
    second_factory = create_session_factory(database_url)

    first_engine = first_factory.kw["bind"]
    second_engine = second_factory.kw["bind"]
    assert inspect(first_engine).get_table_names() == inspect(second_engine).get_table_names()

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()

    assert rows == [(HEAD_REVISION,)]
