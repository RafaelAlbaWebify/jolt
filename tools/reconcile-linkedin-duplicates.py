from __future__ import annotations

import argparse
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

LINKEDIN_JOB_RE = re.compile(r"/jobs/view/(?:[^/?#]*-)?(?P<job_id>\d+)(?:[/?#]|$)")


def linkedin_job_id(source_job_id: str, source_url: str) -> str:
    if source_job_id.strip().isdigit():
        return source_job_id.strip()
    match = LINKEDIN_JOB_RE.search(urlsplit(source_url).path)
    return match.group("job_id") if match else ""


def stable_linkedin_url(job_id: str) -> str:
    return f"https://www.linkedin.com/jobs/view/{job_id}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile duplicate LinkedIn postings by stable source job ID while preserving "
            "source documents and capture evidence. Dry-run is the default."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/jolt.db"),
        help="Path to the JOLT SQLite database (default: data/jolt.db).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the reconciliation. Without this flag, only report planned changes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database = args.database.resolve()
    if not database.exists():
        raise SystemExit(f"Database not found: {database}")

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    rows = connection.execute(
        """
        SELECT ci.id AS capture_item_id,
               ci.source_job_id,
               ci.source_url,
               ci.posting_id,
               p.created_at
          FROM capture_items AS ci
          JOIN postings AS p ON p.id = ci.posting_id
         WHERE ci.posting_id IS NOT NULL
        """
    ).fetchall()

    groups: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        job_id = linkedin_job_id(row["source_job_id"], row["source_url"])
        if job_id:
            groups[job_id].append(row)

    duplicate_groups = {
        job_id: items
        for job_id, items in groups.items()
        if len({item["posting_id"] for item in items}) > 1
    }

    print(f"Database: {database}")
    print(f"Duplicate LinkedIn job groups: {len(duplicate_groups)}")

    merged_postings = 0
    skipped_groups = 0
    try:
        for job_id, items in sorted(duplicate_groups.items()):
            posting_ids = sorted(
                {item["posting_id"] for item in items},
                key=lambda posting_id: min(
                    item["created_at"] for item in items if item["posting_id"] == posting_id
                ),
            )
            keeper_id, *duplicate_ids = posting_ids

            placeholders = ",".join("?" for _ in duplicate_ids)
            protected = connection.execute(
                f"""
                SELECT
                    (SELECT COUNT(*) FROM review_decisions WHERE posting_id IN ({placeholders}))
                    + (SELECT COUNT(*) FROM applications WHERE posting_id IN ({placeholders}))
                    + (SELECT COUNT(*) FROM outcomes WHERE posting_id IN ({placeholders}))
                """,
                [*duplicate_ids, *duplicate_ids, *duplicate_ids],
            ).fetchone()[0]

            print(
                f"LinkedIn job {job_id}: keeper={keeper_id}; "
                f"duplicates={','.join(duplicate_ids)}"
            )
            if protected:
                skipped_groups += 1
                print(f"  SKIP: {protected} human workflow record(s) reference duplicates.")
                continue

            if not args.apply:
                continue

            connection.execute(
                f"UPDATE capture_items SET posting_id = ? WHERE posting_id IN ({placeholders})",
                [keeper_id, *duplicate_ids],
            )
            connection.execute(
                f"""
                UPDATE application_readiness_reports
                   SET posting_id = ?
                 WHERE posting_id IN ({placeholders})
                """,
                [keeper_id, *duplicate_ids],
            )
            connection.execute(
                "UPDATE postings SET canonical_url = ? WHERE id = ?",
                (stable_linkedin_url(job_id), keeper_id),
            )
            connection.execute(
                f"DELETE FROM evaluations WHERE posting_id IN ({placeholders})",
                duplicate_ids,
            )
            connection.execute(
                f"DELETE FROM postings WHERE id IN ({placeholders})",
                duplicate_ids,
            )
            merged_postings += len(duplicate_ids)

        if args.apply:
            connection.commit()
            print(f"Applied. Removed duplicate posting rows: {merged_postings}")
        else:
            connection.rollback()
            print("Dry run only. Re-run with --apply after reviewing this output.")
        if skipped_groups:
            print(f"Groups requiring manual review: {skipped_groups}")
            return 2
        return 0
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
