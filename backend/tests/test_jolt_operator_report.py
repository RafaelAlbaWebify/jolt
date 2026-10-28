from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path
from zipfile import ZipFile


def test_operator_diagnostic_has_only_sanitized_manifest(tmp_path: Path, monkeypatch) -> None:
    source = Path(__file__).resolve().parents[2] / "tools" / "jolt_operator_report.py"
    spec = importlib.util.spec_from_file_location("jolt_operator_report", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    database = tmp_path / "jolt.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE confidential (id INTEGER PRIMARY KEY, secret TEXT)")
        connection.execute("INSERT INTO confidential(secret) VALUES ('not-for-export')")
    monkeypatch.setattr(module, "_git_revision", lambda _root: "a" * 40)
    report = module.build_report(database, tmp_path)
    output = tmp_path / "diagnostic.zip"
    with ZipFile(output, "w") as archive:
        archive.writestr("manifest.json", json.dumps(report))
    with ZipFile(output) as archive:
        assert archive.namelist() == ["manifest.json"]
        payload = archive.read("manifest.json").decode()
    assert "not-for-export" not in payload
    assert report["checkout_sha"] == "a" * 40
    assert report["runtime_api_verified"] is False
    assert report["database"]["table_counts"]["confidential"] == 1
