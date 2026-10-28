from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


def test_read_only_baseline_records_counts_without_mutating_database(tmp_path: Path) -> None:
    module_path = Path(__file__).resolve().parents[2] / "tools" / "jolt_baseline.py"
    spec = importlib.util.spec_from_file_location("jolt_baseline", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    database = tmp_path / "sample.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, secret TEXT)")
        connection.execute("INSERT INTO sample (secret) VALUES ('do-not-export')")
    report = module.collect(database)
    assert report["database_integrity"] == "ok"
    assert report["table_counts"] == {"sample": 1}
    assert report["read_only"] is True
    assert "do-not-export" not in str(report)
    assert "sample.db" == report["database_filename"]


def test_read_only_baseline_does_not_create_missing_database(tmp_path: Path) -> None:
    import pytest

    module_path = Path(__file__).resolve().parents[2] / "tools" / "jolt_baseline.py"
    spec = importlib.util.spec_from_file_location("jolt_baseline", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        module.collect(missing)
    assert not missing.exists()
