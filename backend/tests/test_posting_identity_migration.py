from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def _config(database: Path) -> Config:
    backend_root = Path(__file__).parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.attributes["database_url"] = f"sqlite:///{database.as_posix()}"
    return config


def test_upgrade_backfills_url_and_hash_identity_keys(tmp_path: Path) -> None:
    database = tmp_path / "pre_identity.db"
    config = _config(database)
    command.upgrade(config, "20260727_0014")

    with sqlite3.connect(database) as connection:
        connection.executemany(
            """
            INSERT INTO source_documents
                (id, source_type, source_url, raw_text, content_hash, captured_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "source-url",
                    "manual",
                    "https://example.test/jobs/7",
                    "url text",
                    "a" * 64,
                    "2026-07-27 09:00:00",
                ),
                ("source-hash", "manual", "", "hash text", "b" * 64, "2026-07-27 09:01:00"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO postings
                (id, source_document_id, canonical_url, title, company, location,
                 description, identity_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "posting-url",
                    "source-url",
                    "https://example.test/jobs/7",
                    "Role 7",
                    "Example",
                    "Spain",
                    "url text",
                    "new",
                    "2026-07-27 09:00:00",
                ),
                (
                    "posting-hash",
                    "source-hash",
                    "",
                    "Role hash",
                    "Example",
                    "Remote",
                    "hash text",
                    "new",
                    "2026-07-27 09:01:00",
                ),
            ],
        )
        connection.commit()

    command.upgrade(config, "head")

    with sqlite3.connect(database) as connection:
        rows = connection.execute("SELECT id, identity_key FROM postings ORDER BY id").fetchall()
        columns = connection.execute("PRAGMA table_info(postings)").fetchall()
        indexes = connection.execute("PRAGMA index_list(postings)").fetchall()
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()

    assert rows == [
        ("posting-hash", f"hash:{'b' * 64}"),
        ("posting-url", "url:https://example.test/jobs/7"),
    ]
    identity_column = next(column for column in columns if column[1] == "identity_key")
    assert identity_column[3] == 1
    assert any(row[1] == "uq_postings_identity_key" and row[2] == 1 for row in indexes)
    assert revision == ("20260827_0021",)
