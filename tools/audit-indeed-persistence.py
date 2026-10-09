"""Read-only integrity audit for a supervised Indeed capture ZIP and JOLT SQLite."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path


def audit(db_path: Path, zip_path: Path) -> dict[str, object]:
    with zipfile.ZipFile(zip_path) as archive:
        result = json.loads(archive.read("api_result.json"))
        summary = json.loads(archive.read("capture_summary.json"))
    run_id = result["capture_run_id"]
    expected = {c["source_job_id"]: c for c in summary["cards"]}
    lengths = {
        t["source_job_id"]: t["description_characters"]
        for t in summary["job_timings"]
        if "description_characters" in t
    }
    uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    failures: list[str] = []
    checks: list[dict[str, object]] = []
    try:
        rows = connection.execute(
            """
            SELECT ci.source_job_id, ci.title, ci.company, ci.location,
                   ci.detail_status, sd.raw_text, sd.content_hash AS document_hash,
                   ca.raw_payload, ca.content_hash AS artifact_hash,
                   p.id AS posting_found
            FROM capture_items ci
            LEFT JOIN source_documents sd ON sd.id = ci.source_document_id
            LEFT JOIN capture_artifacts ca ON ca.capture_item_id = ci.id
            LEFT JOIN postings p ON p.id = ci.posting_id
            WHERE ci.capture_run_id = ?
            """,
            (run_id,),
        ).fetchall()
        seen = set()
        for row in rows:
            key = row["source_job_id"]
            seen.add(key)
            errors = []
            source = expected.get(key)
            if source is None:
                errors.append("unexpected_item")
            if row["detail_status"] != "verified":
                errors.append("not_verified")
            if not row["raw_payload"]:
                errors.append("missing_capture_artifact")
            else:
                payload = row["raw_payload"]
                if hashlib.sha256(payload.encode("utf-8")).hexdigest() != row["artifact_hash"]:
                    errors.append("artifact_hash_mismatch")
                item = json.loads(payload)
                description = item.get("description", "")
                if not description:
                    errors.append("empty_description")
                if key in lengths and len(description) != lengths[key]:
                    errors.append("description_length_mismatch")
                if source is not None:
                    for field in ("title", "company", "location"):
                        if item.get(field) != source.get(field) or row[field] != source.get(field):
                            errors.append(f"{field}_mismatch")
                expected_raw = "\n".join(
                    part
                    for part in (
                        item.get("title", ""),
                        item.get("company", ""),
                        f"Location: {item['location']}" if item.get("location") else "",
                        description,
                    )
                    if part
                ).strip()
                if row["raw_text"] != expected_raw:
                    errors.append("source_document_text_mismatch")
            if not row["raw_text"]:
                errors.append("missing_source_document")
            elif hashlib.sha256(row["raw_text"].encode("utf-8")).hexdigest() != row["document_hash"]:
                errors.append("source_document_hash_mismatch")
            if row["posting_found"] is None:
                errors.append("missing_posting")
            failures.extend(f"{key}: {error}" for error in errors)
            checks.append({"source_job_id": key, "passed": not errors, "errors": errors})
        for key in sorted(set(expected) - seen):
            failures.append(f"{key}: missing_capture_item")
    finally:
        connection.close()
    return {
        "status": "passed" if not failures else "failed",
        "capture_run_id": run_id,
        "expected_items": len(expected),
        "checked_items": len(checks),
        "passed_items": sum(c["passed"] for c in checks),
        "failures": failures,
        "checks": checks,
        "scope": "Exact capture artifact and immutable source document; not a comparison with the live Indeed website or normalized Posting.description",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--zip", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.db, args.zip)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
