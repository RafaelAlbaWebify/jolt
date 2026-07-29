from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


def default_db_path() -> Path:
    return Path(__file__).resolve().parents[1] / "backend" / "data" / "jolt.db"


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def scalar(connection: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = connection.execute(sql, params).fetchone()
    return int(row[0] or 0) if row else 0


def fetch_rows(connection: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    sql = """
    WITH latest_evaluation AS (
      SELECT e.*
      FROM evaluations e
      JOIN (
        SELECT posting_id, MAX(created_at) AS max_created_at
        FROM evaluations
        GROUP BY posting_id
      ) latest
        ON latest.posting_id = e.posting_id
       AND latest.max_created_at = e.created_at
    ), latest_review AS (
      SELECT r.*
      FROM review_decisions r
      JOIN (
        SELECT posting_id, MAX(reviewed_at) AS max_reviewed_at
        FROM review_decisions
        GROUP BY posting_id
      ) latest
        ON latest.posting_id = r.posting_id
       AND latest.max_reviewed_at = r.reviewed_at
    )
    SELECT
      p.id AS posting_id,
      p.title,
      p.company,
      p.location,
      p.created_at,
      p.source_document_id,
      sd.source_type,
      sd.source_url,
      le.id AS evaluation_id,
      le.ranking_score,
      le.recommendation,
      lr.decision AS review_decision,
      a.id AS application_id,
      ci.id AS capture_item_id,
      ci.capture_run_id,
      cr.status AS capture_run_status,
      CASE WHEN ci.id IS NOT NULL THEN 1 ELSE 0 END AS has_capture_item,
      CASE WHEN lr.id IS NOT NULL THEN 1 ELSE 0 END AS has_review,
      CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END AS has_application
    FROM postings p
    LEFT JOIN source_documents sd ON sd.id = p.source_document_id
    LEFT JOIN latest_evaluation le ON le.posting_id = p.id
    LEFT JOIN latest_review lr ON lr.posting_id = p.id
    LEFT JOIN applications a ON a.posting_id = p.id
    LEFT JOIN capture_items ci ON ci.posting_id = p.id
    LEFT JOIN capture_runs cr ON cr.id = ci.capture_run_id
    ORDER BY p.created_at DESC
    LIMIT ?
    """
    return list(connection.execute(sql, (limit,)))


def classify(row: sqlite3.Row) -> str:
    if row["has_application"]:
        return "tracked_application"
    if row["has_review"]:
        return "reviewed_classified"
    if row["has_capture_item"]:
        return "pending_capture_backed_review"
    if row["source_type"] in {"linkedin_live", "linkedin_fixture"}:
        return "orphaned_linkedin_import"
    if (row["source_url"] or "").lower().find("linkedin.com") >= 0:
        return "orphaned_linkedin_url_unknown_type"
    return "manual_or_legacy_unlinked"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit why JOLT opportunities are visible in the queue.")
    parser.add_argument("--db", type=Path, default=default_db_path())
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    db_path = args.db.resolve()
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    output_dir = (args.output_dir or (Path.home() / "Downloads" / "JOLT_OPPORTUNITY_DB_AUDIT")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        tables = [
            "source_documents",
            "postings",
            "evaluations",
            "review_decisions",
            "applications",
            "capture_runs",
            "capture_items",
            "professional_capture_runs",
            "professional_capture_artifacts",
        ]
        counts = {
            table: scalar(connection, f"SELECT COUNT(*) FROM {table}") if table_exists(connection, table) else None
            for table in tables
        }
        rows = fetch_rows(connection, args.limit)
        enriched: list[dict[str, Any]] = []
        classifications: Counter[str] = Counter()
        source_types: Counter[str] = Counter()
        for row in rows:
            item = dict(row)
            item["queue_classification"] = classify(row)
            classifications[item["queue_classification"]] += 1
            source_types[str(item.get("source_type") or "<null>")] += 1
            enriched.append(item)

        summary = {
            "db_path": str(db_path),
            "counts": counts,
            "audited_posting_rows": len(enriched),
            "queue_classifications": dict(classifications),
            "source_types_in_audited_rows": dict(source_types),
            "sample_titles": [
                {
                    "title": item["title"],
                    "company": item["company"],
                    "source_type": item["source_type"],
                    "has_capture_item": bool(item["has_capture_item"]),
                    "has_review": bool(item["has_review"]),
                    "has_application": bool(item["has_application"]),
                    "queue_classification": item["queue_classification"],
                }
                for item in enriched[:20]
            ],
        }

        json_path = output_dir / "jolt_opportunity_db_audit.json"
        csv_path = output_dir / "jolt_opportunity_db_audit.csv"
        json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            if enriched:
                writer = csv.DictWriter(handle, fieldnames=list(enriched[0].keys()))
                writer.writeheader()
                writer.writerows(enriched)

        print(json.dumps(summary, indent=2, ensure_ascii=False))
        print(f"\nWrote: {json_path}")
        print(f"Wrote: {csv_path}")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
