from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

PREVIOUS_REVISION = "20260712_0003"
CURRENT_REVISION = "20260724_0010"
TABLE_NAME = "application_readiness_reports"
INDEX_NAME = "ix_application_readiness_reports_posting_id"


def _prepare_versioned_database(database_path: Path, *, readiness_table_exists: bool) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE postings (id VARCHAR(36) PRIMARY KEY NOT NULL)")
        if readiness_table_exists:
            connection.execute(
                """
                CREATE TABLE application_readiness_reports (
                    id VARCHAR(36) PRIMARY KEY NOT NULL,
                    posting_id VARCHAR(36) NOT NULL,
                    profile_version_id VARCHAR(80) NOT NULL,
                    engine_version VARCHAR(50) NOT NULL,
                    priority VARCHAR(20) NOT NULL,
                    readiness_score INTEGER NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(posting_id) REFERENCES postings (id)
                )
                """
            )
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.execute(
            "INSERT INTO alembic_version (version_num) VALUES (?)", (PREVIOUS_REVISION,)
        )
        connection.commit()


def _upgrade(database_path: Path, monkeypatch) -> None:
    backend_root = Path(__file__).parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    monkeypatch.setenv("JOLT_DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    command.upgrade(config, "head")


def _assert_readiness_schema(database_path: Path) -> None:
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    inspector = inspect(engine)

    assert inspector.has_table(TABLE_NAME)
    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    assert columns == {
        "id",
        "posting_id",
        "profile_version_id",
        "engine_version",
        "priority",
        "readiness_score",
        "report_json",
        "created_at",
    }
    indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    assert INDEX_NAME in indexes

    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert revision == (CURRENT_REVISION,)


def test_upgrade_creates_readiness_table_from_previous_schema(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "pre_readiness.db"
    _prepare_versioned_database(database_path, readiness_table_exists=False)

    _upgrade(database_path, monkeypatch)

    _assert_readiness_schema(database_path)


def test_upgrade_adopts_table_previously_created_by_metadata(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "metadata_created.db"
    _prepare_versioned_database(database_path, readiness_table_exists=True)

    _upgrade(database_path, monkeypatch)

    _assert_readiness_schema(database_path)
