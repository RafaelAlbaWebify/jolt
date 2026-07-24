from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_creates_expected_schema(tmp_path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "migration.db"
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

    command.upgrade(config, "head")

    tables = set(inspect(create_engine(f"sqlite:///{database_path.as_posix()}")).get_table_names())
    assert {
        "alembic_version",
        "source_documents",
        "capture_runs",
        "capture_pages",
        "capture_items",
        "profile_versions",
        "postings",
        "evaluations",
        "review_decisions",
        "applications",
        "application_events",
        "application_tasks",
        "application_interviews",
        "application_contacts",
        "application_documents",
        "professional_source_overrides",
        "outcomes",
    }.issubset(tables)
