from __future__ import annotations

from pathlib import Path

import pytest

from jolt.certification_isolation import (
    validate_certification_runtime_identity,
)


def _identity(database_url: str, database_path: str | None) -> dict[str, object]:
    return {
        "database": {
            "database_url": database_url,
            "database_path": database_path,
        }
    }


@pytest.mark.parametrize(
    ("database_url", "database_path"),
    [
        (
            "sqlite:////tmp/jolt-full-cycle-certification-abc123.db",
            "/tmp/jolt-full-cycle-certification-abc123.db",
        ),
        (
            "sqlite:///C:/Temp/jolt-full-cycle-certification-abc123.db",
            r"C:\Temp\jolt-full-cycle-certification-abc123.db",
        ),
        (
            "sqlite:////tmp/jolt-full-cycle-certification.db",
            "/tmp/jolt-full-cycle-certification.db",
        ),
    ],
)
def test_accepts_explicit_certification_database(
    database_url: str,
    database_path: str,
) -> None:
    result = validate_certification_runtime_identity(_identity(database_url, database_path))

    assert result == Path(database_path)


@pytest.mark.parametrize(
    ("database_url", "database_path"),
    [
        ("sqlite:///jolt.db", "jolt.db"),
        ("sqlite:///backend/jolt.db", "backend/jolt.db"),
        (
            "sqlite:///C:/Users/ralba/Documents/GitHub/jolt/backend/jolt.db",
            r"C:\Users\ralba\Documents\GitHub\jolt\backend\jolt.db",
        ),
        ("postgresql://localhost/jolt", None),
        ("sqlite:///:memory:", None),
        ("sqlite:///temporary-test.db", "temporary-test.db"),
    ],
)
def test_rejects_normal_or_unmarked_database(
    database_url: str,
    database_path: str | None,
) -> None:
    with pytest.raises(RuntimeError):
        validate_certification_runtime_identity(_identity(database_url, database_path))


def test_rejects_missing_database_identity() -> None:
    with pytest.raises(RuntimeError, match="no database section"):
        validate_certification_runtime_identity({})
