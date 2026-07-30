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

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    tables = set(inspector.get_table_names())
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
        "professional_capture_runs",
        "professional_capture_artifacts",
        "professional_evidence_settings",
        "linkedin_presence_captures",
        "linkedin_presence_recommendations",
        "outcomes",
    }.issubset(tables)

    run_columns = {column["name"] for column in inspector.get_columns("professional_capture_runs")}
    assert {
        "authorized_at",
        "authorization_expires_at",
        "user_present_confirmed",
    }.issubset(run_columns)
    artifact_columns = {
        column["name"] for column in inspector.get_columns("professional_capture_artifacts")
    }
    assert {"completeness_status", "retention_days"}.issubset(artifact_columns)
    linkedin_capture_columns = {
        column["name"] for column in inspector.get_columns("linkedin_presence_captures")
    }
    assert {"category", "content_hash", "previous_capture_id", "changed_since_previous"}.issubset(
        linkedin_capture_columns
    )
    linkedin_recommendation_columns = {
        column["name"] for column in inspector.get_columns("linkedin_presence_recommendations")
    }
    assert {"recommendation_type", "priority", "status", "proposed_text"}.issubset(
        linkedin_recommendation_columns
    )
