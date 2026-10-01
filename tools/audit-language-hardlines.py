from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_SRC = _REPO_ROOT / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from jolt.job_search_preferences import load_job_search_preferences  # noqa: E402
from jolt.language_hardline import analyze_language_evidence  # noqa: E402


def _database_path() -> Path:
    configured = os.getenv("JOLT_DATABASE_URL", "").strip()
    if configured:
        parsed = urlparse(configured)
        if parsed.scheme != "sqlite":
            raise SystemExit("This read-only audit supports JOLT's SQLite database only.")
        raw_path = unquote(parsed.path)
        if os.name == "nt" and raw_path.startswith("/") and len(raw_path) > 2:
            raw_path = raw_path[1:]
        return Path(raw_path)
    return Path(__file__).resolve().parents[1] / "backend" / "data" / "jolt.db"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only audit of current non-rejected AI reviews against deterministic "
            "job-ad language and mandatory-language hardlines."
        )
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--include-source-text", action="store_true")
    args = parser.parse_args()

    database = _database_path().resolve()
    if not database.exists():
        raise SystemExit(f"JOLT database not found: {database}")

    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT
            ar.id AS ai_review_id,
            ar.posting_id,
            ar.decision,
            ar.language_status,
            ar.hardline_status,
            ar.technical_fit,
            ar.reviewed_at,
            ar.imported_at,
            p.title,
            p.company,
            p.location,
            sd.source_url,
            sd.raw_text
        FROM ai_reviews AS ar
        JOIN postings AS p ON p.id = ar.posting_id
        JOIN source_documents AS sd ON sd.id = p.source_document_id
        ORDER BY ar.imported_at DESC, ar.reviewed_at DESC, ar.id DESC
        """
    ).fetchall()
    connection.close()

    latest_by_posting: dict[str, sqlite3.Row] = {}
    for row in rows:
        latest_by_posting.setdefault(str(row["posting_id"]), row)

    preferences = load_job_search_preferences()
    findings: list[dict[str, object]] = []
    current_non_rejected = 0

    for row in latest_by_posting.values():
        if str(row["decision"] or "") == "reject":
            continue
        current_non_rejected += 1
        result = analyze_language_evidence(
            source_text=str(row["raw_text"] or ""),
            preferences=preferences,
        )
        if not result.hardline_reject and not result.manual_review:
            continue

        finding: dict[str, object] = {
            "ai_review_id": row["ai_review_id"],
            "posting_id": row["posting_id"],
            "title": row["title"],
            "company": row["company"],
            "location": row["location"],
            "current_decision": row["decision"],
            "current_language_status": row["language_status"],
            "current_hardline_status": row["hardline_status"],
            "technical_fit": row["technical_fit"],
            "source_url": row["source_url"],
            "new_resolution": "reject" if result.hardline_reject else "manual_review",
            "language_hardline_evidence": result.as_dict(),
        }
        if args.include_source_text:
            finding["source_text"] = row["raw_text"]
        findings.append(finding)

    hard_rejects = [item for item in findings if item["new_resolution"] == "reject"]
    manual_reviews = [item for item in findings if item["new_resolution"] == "manual_review"]

    payload = {
        "audit_type": "jolt_language_hardline_audit",
        "database_read_only": True,
        "candidate_languages": preferences.languages,
        "candidate_language_levels": preferences.language_levels,
        "current_non_rejected_reviews": current_non_rejected,
        "potentially_affected": len(findings),
        "hard_reject_count": len(hard_rejects),
        "manual_review_count": len(manual_reviews),
        "unsupported_job_language_count": sum(
            "UNSUPPORTED_JOB_LANGUAGE"
            in item["language_hardline_evidence"]["reason_codes"]
            for item in hard_rejects
        ),
        "unmet_mandatory_language_count": sum(
            "LANGUAGE_REQUIREMENT_UNMET"
            in item["language_hardline_evidence"]["reason_codes"]
            for item in hard_rejects
        ),
        "findings": findings,
    }

    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output is not None:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(output),
                    "potentially_affected": len(findings),
                    "hard_reject_count": len(hard_rejects),
                    "manual_review_count": len(manual_reviews),
                },
                indent=2,
            )
        )
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
