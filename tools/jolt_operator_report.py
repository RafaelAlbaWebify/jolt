"""Generate a redacted, read-only JOLT operator diagnostic ZIP.

Example: python tools/jolt_operator_report.py backend/data/jolt.db --output JOLT_DIAGNOSTIC.zip
No backend service, credentials, browser session or source descriptions are accessed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def _baseline_module():
    source = Path(__file__).with_name("jolt_baseline.py")
    spec = importlib.util.spec_from_file_location("jolt_baseline", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the JOLT baseline diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_revision(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    sha = result.stdout.strip()
    return sha if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha) else None


def _processing_snapshot(database: Path) -> dict[str, object]:
    """Count module evidence without claiming AI completion from Market extraction."""
    started = time.perf_counter()
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.execute("PRAGMA query_only = ON")
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        required = {"capture_items", "market_intelligence_observations", "ai_reviews"}
        if not required.issubset(tables):
            return {
                "state": "unknown",
                "reason": "Required tables not present in this schema",
                "seconds": round(time.perf_counter() - started, 4),
            }
        verified = {
            (str(run), str(job))
            for run, job in conn.execute(
                "SELECT capture_run_id, source_job_id FROM capture_items "
                "WHERE detail_status = 'verified' AND posting_id IS NOT NULL "
                "AND source_document_id IS NOT NULL"
            )
        }
        market = {
            (str(run), str(job))
            for run, job in conn.execute(
                "SELECT source_capture_run_id, source_job_id "
                "FROM market_intelligence_observations"
            )
        }
        reviewed = int(conn.execute("SELECT COUNT(*) FROM ai_reviews").fetchone()[0])
    return {
        "state": "partial_evidence_inventory",
        "market_verified_identities": len(verified),
        "market_observation_identities": len(market),
        "market_missing_identities": len(verified - market),
        "market_unexpected_identities": len(market - verified),
        "ai_review_records": reviewed,
        "review_coverage": "unknown: reviews may reference repeated captures and versions",
        "other_modules": "unknown: do not interpret market integration as processing completion",
        "seconds": round(time.perf_counter() - started, 4),
    }


def _journal_summary(project_root: Path) -> dict[str, object]:
    """Summarize interrupted imports without exporting package IDs or payloads."""
    path = project_root / "backend" / "data" / "unified_import_journal.json"
    if not path.exists():
        return {"state": "absent", "completed": 0, "requires_reconciliation": 0}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Invalid journal shape")
        entries = list(payload.values())
        if not all(isinstance(entry, dict) for entry in entries):
            raise ValueError("Invalid journal entry")
    except (OSError, ValueError, json.JSONDecodeError):
        return {"state": "unreadable", "requires_reconciliation": "unknown"}
    completed = sum(entry.get("state") == "completed" for entry in entries)
    return {
        "state": "readable",
        "completed": completed,
        "requires_reconciliation": len(entries) - completed,
        "incomplete_last_steps": sorted({
            str(entry.get("last_step") or "not_started")
            for entry in entries
            if entry.get("state") != "completed"
        }),
    }


def build_report(database: Path, project_root: Path) -> dict[str, object]:
    baseline = _baseline_module().collect(database)
    return {
        "contract": "jolt_operator_diagnostic",
        "version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "checkout_sha": _git_revision(project_root),
        "data_origin": "local_sqlite_read_only",
        "runtime_api_verified": False,
        "browser_verified": False,
        "database": baseline,
        "processing": _processing_snapshot(database),
        "import_recovery": _journal_summary(project_root),
        "limitations": [
            "No backend API or frontend checks have been executed",
            "No capture text, application contents, identities or logs are included",
            "Row counts are snapshots; concurrent database writes may change them",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.database.resolve():
        parser.error("Output must differ from database")
    report = build_report(args.database, Path(__file__).resolve().parents[1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(report, indent=2, sort_keys=True))
    print(f"Diagnostic created: {args.output}")


if __name__ == "__main__":
    main()
