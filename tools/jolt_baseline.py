"""Read-only, redacted SQLite baseline for the JOLT modernization program.

Usage: python tools/jolt_baseline.py backend/data/jolt.db --output report.json
Never opens a write-capable connection; report contains schema/table metadata only.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path


def collect(db_path: Path) -> dict[str, object]:
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    started = time.perf_counter()
    # SQLite URI mode=ro avoids creating/upgrading/migrating any database.
    uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        connection.execute("PRAGMA query_only = ON")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
        free_pages = int(connection.execute("PRAGMA freelist_count").fetchone()[0])
        index_count = int(
            connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'").fetchone()[0]
        )
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {}
        for name in tables:
            escaped = name.replace('"', '""')
            counts[name] = connection.execute(
                f'SELECT COUNT(*) FROM "{escaped}"'
            ).fetchone()[0]
        revision = None
        if "alembic_version" in counts:
            revision = [
                row[0] for row in connection.execute(
                    "SELECT version_num FROM alembic_version"
                )
            ]
    finally:
        connection.close()
    return {
        "report_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "database_filename": db_path.name,
        "database_bytes": db_path.stat().st_size,
        "database_integrity": integrity,
        "sqlite_page_size_bytes": page_size,
        "sqlite_page_count": page_count,
        "sqlite_free_page_count": free_pages,
        "sqlite_estimated_free_bytes": free_pages * page_size,
        "sqlite_index_count": index_count,
        "schema_revisions": revision,
        "table_counts": counts,
        "table_count": len(tables),
        "collection_seconds": round(time.perf_counter() - started, 4),
        "read_only": True,
        "excludes": "raw source text, job descriptions, user records, tokens and identifiers",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = collect(args.database)
    if args.output.resolve() == args.database.resolve():
        parser.error("Report path must not point to the database")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, args.output)
    print(json.dumps({"report": str(args.output), "integrity": report["database_integrity"], "tables": report["table_count"]}))


if __name__ == "__main__":
    main()
