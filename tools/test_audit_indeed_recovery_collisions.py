"""Regression checks for read-only Indeed recovery collision audit."""
import importlib.util
import json
import sqlite3
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("audit-indeed-recovery-collisions.py")
spec = importlib.util.spec_from_file_location("jolt_recovery_collision_audit", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_classifies_existing_and_new_without_database_mutation(tmp_path: Path):
    db = tmp_path / "jolt.db"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE posting_source_identities (portal TEXT, source_job_id TEXT)")
        con.execute("CREATE TABLE postings (canonical_url TEXT)")
        con.execute(
            "INSERT INTO posting_source_identities VALUES ('indeed', 'existing')"
        )
        con.execute(
            "INSERT INTO postings VALUES ('https://es.indeed.com/viewjob?jk=url_only')"
        )
    items = [
        {"source_job_id": key, "identity_verified": True, "description": "Evidence"}
        for key in ("existing", "url_only", "new")
    ]
    archive = tmp_path / "capture.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr("api_result.json", json.dumps({
            "validation_errors": [{"input": items}]
        }))
        out.writestr("capture_summary.json", json.dumps({
            "captured_count": 3, "max_jobs": 200,
            "pages": [{"page_number": 1}], "search_url": "https://es.indeed.com/jobs"
        }))
    original = db.read_bytes()
    report = module.audit(archive, db)
    assert report["requested"] == 3
    assert report["already_registered"] == 1
    assert report["not_registered"] == 2
    assert report["possible_unregistered_url_duplicates"] == 1
    assert report["safe_to_import_automatically"] is False
    assert db.read_bytes() == original


def test_audit_detects_historical_capture_and_legacy_document(tmp_path: Path):
    db = tmp_path / "jolt.db"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE posting_source_identities (portal TEXT, source_job_id TEXT)")
        con.execute("CREATE TABLE postings (canonical_url TEXT)")
        con.execute("CREATE TABLE capture_runs (id TEXT, source TEXT)")
        con.execute("CREATE TABLE capture_items (capture_run_id TEXT, source_job_id TEXT)")
        con.execute("CREATE TABLE source_documents (source_type TEXT, source_url TEXT)")
        con.execute("INSERT INTO capture_runs VALUES ('one','indeed')")
        con.execute("INSERT INTO capture_items VALUES ('one','historic')")
        con.execute("INSERT INTO source_documents VALUES ('indeed_live','https://es.indeed.com/viewjob?jk=legacy')")
    items = [
        {"source_job_id": key, "identity_verified": True, "description": "Evidence"}
        for key in ("historic", "legacy")
    ]
    archive = tmp_path / "capture.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr("api_result.json", json.dumps({
            "validation_errors": [{"input": items}]
        }))
        out.writestr("capture_summary.json", json.dumps({
            "captured_count": 2, "max_jobs": 200,
            "pages": [{"page_number": 1}], "search_url": "https://es.indeed.com/jobs"
        }))
    report = module.audit(archive, db)
    assert report["previously_captured_identifiers"] == 1
    assert report["legacy_source_document_matches"] == 1
