"""Read-only recovery collision audit against operator SQLite.

Never opens the database for writing. Never imports into JOLT.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

PREFLIGHT = Path(__file__).with_name("preflight-indeed-recovery.py")
spec = importlib.util.spec_from_file_location("jolt_indeed_recovery_preflight", PREFLIGHT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def audit(zip_path: Path, db_path: Path) -> dict:
    archive = module.inspect_archive(zip_path)
    items = archive["recovered_request"]["items"]
    if not db_path.is_file():
        raise ValueError("Database not found. Explicitly provide the active JOLT DB path.")
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()
    uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "posting_source_identities" not in tables:
            raise ValueError("Missing posting_source_identities table; migrations required")
        known = set()
        for row in connection.execute(
            "SELECT source_job_id FROM posting_source_identities WHERE portal = ?",
            ("indeed",),
        ):
            known.add(row[0])
        incoming = {item["source_job_id"] for item in items}
        matched = incoming & known
        new = incoming - known
        # Existing same-URL postings without source registry are uncertain.
        # Their identity must be inspected before any import.
        if "postings" not in tables:
            raise ValueError("Missing postings table")
        urls = {row[0] for row in connection.execute(
            "SELECT canonical_url FROM postings WHERE canonical_url LIKE '%indeed.com/%'"
        )}
        potential = []
        for item in items:
            key = item["source_job_id"]
            if key in new and any(("jk=" + key) in url for url in urls if isinstance(url, str)):
                potential.append(key)
    finally:
        connection.close()
    after = hashlib.sha256(db_path.read_bytes()).hexdigest()
    if before != after:
        raise RuntimeError("Database file changed during read-only audit; abort")
    return {
        "contract": "jolt-indeed-recovery-collision-audit-v1",
        "archive_sha256": archive["archive_sha256"],
        "db_sha256_unchanged": before == after,
        "requested": len(items),
        "already_registered": len(matched),
        "not_registered": len(new),
        "possible_unregistered_url_duplicates": len(potential),
        "safe_to_import_automatically": False,
        "requires_transactional_idempotent_importer": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.zip, args.db)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
