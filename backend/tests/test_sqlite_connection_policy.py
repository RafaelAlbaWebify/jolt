from pathlib import Path

from sqlalchemy import text

from jolt.database import create_session_factory


def test_sqlite_connections_enable_relational_and_concurrency_pragmas(tmp_path: Path) -> None:
    database = tmp_path / "policy.db"
    factory = create_session_factory(f"sqlite:///{database.as_posix()}")

    with factory() as session:
        foreign_keys = session.execute(text("PRAGMA foreign_keys")).scalar_one()
        busy_timeout = session.execute(text("PRAGMA busy_timeout")).scalar_one()
        journal_mode = session.execute(text("PRAGMA journal_mode")).scalar_one()

    assert foreign_keys == 1
    assert busy_timeout == 5000
    assert journal_mode == "wal"


def test_sqlite_wal_policy_survives_new_session_factory(tmp_path: Path) -> None:
    database = tmp_path / "restart.db"
    first = create_session_factory(f"sqlite:///{database.as_posix()}")
    with first() as session:
        assert session.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"

    restarted = create_session_factory(f"sqlite:///{database.as_posix()}")
    with restarted() as session:
        assert session.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
        assert session.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
