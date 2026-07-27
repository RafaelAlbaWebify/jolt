from pathlib import Path

from jolt import database


def test_default_database_url_is_backend_relative_and_cwd_independent(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("JOLT_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    database_url = database.default_database_url()

    expected_path = Path(database.__file__).resolve().parents[2] / "data" / "jolt.db"
    actual_path = Path(database_url.removeprefix("sqlite:///"))
    assert actual_path == expected_path


def test_configured_database_url_still_takes_precedence(monkeypatch) -> None:
    configured = "sqlite:///C:/custom/jolt.db"
    monkeypatch.setenv("JOLT_DATABASE_URL", configured)

    assert database.default_database_url() == configured
