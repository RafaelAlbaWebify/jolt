from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

_REMOTE_SIGNAL = re.compile(
    r"\b(?:remote|fully\s+remote|work\s+from\s+anywhere|teletrabajo)\b",
    re.IGNORECASE,
)
_REVIEW_DECISIONS = {"strong_pursue", "pursue", "conditional"}


def _database_path() -> Path:
    configured = os.getenv("JOLT_DATABASE_URL", "").strip()
    if configured:
        parsed = urlparse(configured)
        if parsed.scheme != "sqlite":
            raise SystemExit("This read-only audit currently supports JOLT's SQLite production database.")
        raw_path = unquote(parsed.path)
        if os.name == "nt" and raw_path.startswith("/") and len(raw_path) > 2:
            raw_path = raw_path[1:]
        return Path(raw_path)

    return Path(__file__).resolve().parents[1] / "backend" / "data" / "jolt.db"


def _parse_timestamp(value: str) -> datetime | None:
    candidate = value.strip()
    if not candidate:
        return None
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only audit for recent LinkedIn reviews that lack authoritative "
            "location/work-model verification."
        )
    )
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--match", default="", help="Optional case-insensitive title/company/location filter.")
    args = parser.parse_args()

    path = _database_path().resolve()
    if not path.exists():
        raise SystemExit(f"JOLT database not found: {path}")

    uri = f"file:{path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(ai_reviews)").fetchall()
    }
    required = {
        "source_conflict",
        "linkedin_work_model",
        "official_work_model",
        "authoritative_source",
        "remote_status",
        "location_verification_status",
        "source_confidence",
    }
    missing = sorted(required - columns)
    if missing:
        raise SystemExit(
            "Database has not been migrated to source-verification schema; missing: "
            + ", ".join(missing)
        )

    rows = connection.execute(
        """
        SELECT
            ar.id AS ai_review_id,
            ar.posting_id,
            ar.decision,
            ar.geography_status,
            ar.location_eligibility,
            ar.technical_fit,
            ar.reviewed_at,
            ar.source_conflict,
            ar.linkedin_work_model,
            ar.official_work_model,
            ar.authoritative_source,
            ar.official_source_url,
            ar.remote_status,
            ar.location_verification_status,
            ar.source_confidence,
            p.title,
            p.company,
            p.location,
            p.canonical_url,
            sd.source_type,
            sd.source_url,
            sd.raw_text
        FROM ai_reviews AS ar
        JOIN postings AS p ON p.id = ar.posting_id
        JOIN source_documents AS sd ON sd.id = p.source_document_id
        WHERE sd.source_type LIKE 'linkedin%'
        ORDER BY ar.reviewed_at DESC
        """
    ).fetchall()
    connection.close()

    cutoff = datetime.now(UTC) - timedelta(days=max(args.days, 0))
    needle = args.match.casefold().strip()
    findings: list[dict[str, object]] = []

    for row in rows:
        reviewed_at = _parse_timestamp(str(row["reviewed_at"] or ""))
        if reviewed_at is not None and reviewed_at < cutoff:
            continue

        haystack = " ".join(
            str(row[key] or "")
            for key in ("title", "company", "location", "canonical_url", "source_url")
        )
        if needle and needle not in haystack.casefold():
            continue

        raw_text = str(row["raw_text"] or "")
        remote_signal = bool(_REMOTE_SIGNAL.search(str(row["location"] or ""))) or bool(
            _REMOTE_SIGNAL.search(raw_text)
        )
        decision = str(row["decision"] or "")
        verification = str(row["location_verification_status"] or "unverified")
        conflict = bool(row["source_conflict"])

        needs_revalidation = (
            decision in _REVIEW_DECISIONS
            and (
                conflict
                or verification != "verified"
                or str(row["remote_status"] or "") in {"unknown", "not_confirmed_remote"}
                or (
                    remote_signal
                    and str(row["authoritative_source"] or "") not in {
                        "official_ats",
                        "official_careers",
                        "company_site",
                    }
                )
            )
        )
        if not needs_revalidation:
            continue

        findings.append(
            {
                "ai_review_id": row["ai_review_id"],
                "posting_id": row["posting_id"],
                "title": row["title"],
                "company": row["company"],
                "location": row["location"],
                "decision": decision,
                "geography_status": row["geography_status"],
                "location_eligibility": row["location_eligibility"],
                "technical_fit": row["technical_fit"],
                "linkedin_source_url": row["source_url"] or row["canonical_url"],
                "text_remote_signal": remote_signal,
                "source_conflict": conflict,
                "linkedin_work_model": row["linkedin_work_model"],
                "official_work_model": row["official_work_model"],
                "authoritative_source": row["authoritative_source"],
                "official_source_url": row["official_source_url"],
                "remote_status": row["remote_status"],
                "location_verification_status": verification,
                "source_confidence": row["source_confidence"],
                "reviewed_at": str(row["reviewed_at"] or ""),
                "audit_reason": (
                    "Recent LinkedIn-origin review is positive/conditional but authoritative "
                    "location/work-model verification is missing or conflicting."
                ),
            }
        )

    print(
        json.dumps(
            {
                "database": str(path),
                "window_days": args.days,
                "match": args.match,
                "finding_count": len(findings),
                "findings": findings,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
