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


def _market_discrepancy_causes(database: Path) -> dict[str, object]:
    """Classify unmatched market identities without revealing vacancy identifiers."""
    started = time.perf_counter()
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.execute("PRAGMA query_only = ON")
        missing_rows = conn.execute(
            """
            SELECT c.detail_status, r.source, r.status, COUNT(*)
            FROM (
                SELECT DISTINCT capture_run_id, source_job_id, detail_status
                FROM capture_items
                WHERE detail_status = 'verified'
                  AND posting_id IS NOT NULL
                  AND source_document_id IS NOT NULL
            ) AS c
            LEFT JOIN market_intelligence_observations AS o
              ON o.source_capture_run_id = c.capture_run_id
             AND o.source_job_id = c.source_job_id
            LEFT JOIN capture_runs AS r ON r.id = c.capture_run_id
            WHERE o.id IS NULL
            GROUP BY c.detail_status, r.source, r.status
            """
        ).fetchall()
        unexpected_rows = conn.execute(
            """
            SELECT
                CASE
                  WHEN c.id IS NULL THEN 'no_capture_item'
                  WHEN c.detail_status != 'verified' THEN 'not_verified'
                  WHEN c.posting_id IS NULL THEN 'missing_posting_link'
                  WHEN c.source_document_id IS NULL THEN 'missing_document_link'
                  ELSE 'other'
                END AS cause,
                r.source,
                r.status,
                COUNT(*)
            FROM market_intelligence_observations AS o
            LEFT JOIN capture_items AS c
              ON c.id = (
                SELECT ci.id FROM capture_items AS ci
                WHERE ci.capture_run_id = o.source_capture_run_id
                  AND ci.source_job_id = o.source_job_id
                ORDER BY (ci.detail_status = 'verified'
                          AND ci.posting_id IS NOT NULL
                          AND ci.source_document_id IS NOT NULL) DESC,
                         ci.id DESC
                LIMIT 1
              )
            LEFT JOIN capture_runs AS r ON r.id = o.source_capture_run_id
            WHERE NOT EXISTS (
                SELECT 1 FROM capture_items AS verified
                WHERE verified.capture_run_id = o.source_capture_run_id
                  AND verified.source_job_id = o.source_job_id
                  AND verified.detail_status = 'verified'
                  AND verified.posting_id IS NOT NULL
                  AND verified.source_document_id IS NOT NULL
            )
            GROUP BY cause, r.source, r.status
            """
        ).fetchall()
    return {
        "missing_by_source_and_run_status": [
            {"source": source or "unknown", "run_status": status or "unknown", "count": count}
            for _detail, source, status, count in missing_rows
        ],
        "unexpected_by_reason_source_and_run_status": [
            {
                "reason": reason,
                "source": source or "unknown",
                "run_status": status or "unknown",
                "count": count,
            }
            for reason, source, status, count in unexpected_rows
        ],
        "seconds": round(time.perf_counter() - started, 4),
        "read_only": True,
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
        "market_discrepancy_causes": _market_discrepancy_causes(database),
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
