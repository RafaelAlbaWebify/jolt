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


def test_processing_snapshot_labels_missing_modules_as_unknown(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / "tools" / "jolt_operator_report.py"
    spec = importlib.util.spec_from_file_location("jolt_operator_report", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    database = tmp_path / "coverage.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE capture_items (capture_run_id TEXT, source_job_id TEXT, "
            "detail_status TEXT, posting_id TEXT, source_document_id TEXT)"
        )
        connection.execute(
            "CREATE TABLE market_intelligence_observations "
            "(source_capture_run_id TEXT, source_job_id TEXT)"
        )
        connection.execute("CREATE TABLE ai_reviews (id TEXT)")
        connection.executemany(
            "INSERT INTO capture_items VALUES (?, ?, 'verified', 'posting', 'source')",
            [("run-1", "job-1"), ("run-1", "job-2")],
        )
        connection.execute("INSERT INTO market_intelligence_observations VALUES ('run-1', 'job-1')")
    coverage = module._processing_snapshot(database)
    assert coverage["market_verified_identities"] == 2
    assert coverage["market_observation_identities"] == 1
    assert coverage["market_missing_identities"] == 1
    assert coverage["review_coverage"].startswith("unknown:")
    assert coverage["other_modules"].startswith("unknown:")


def test_operator_report_redacts_import_journal_identifiers(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / "tools" / "jolt_operator_report.py"
    spec = importlib.util.spec_from_file_location("jolt_operator_report", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    journal = tmp_path / "backend" / "data" / "unified_import_journal.json"
    journal.parent.mkdir(parents=True)
    journal.write_text(
        json.dumps(
            {
                "private-package-id": {
                    "state": "applying",
                    "last_step": "market_insights",
                    "digest": "secret-digest",
                },
                "another-package-id": {"state": "completed", "last_step": "complete"},
            }
        ),
        encoding="utf-8",
    )
    summary = module._journal_summary(tmp_path)
    assert summary["requires_reconciliation"] == 1
    assert summary["completed"] == 1
    assert summary["incomplete_last_steps"] == ["market_insights"]
    assert "private-package-id" not in str(summary)
    assert "secret-digest" not in str(summary)
