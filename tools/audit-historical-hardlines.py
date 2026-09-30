from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

_POSITIVE = {"pursue", "strong_pursue"}

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "language",
        re.compile(
            r"(?:\b(?:required|mandatory|must|fluency|fluent|proficiency|written|spoken)\b.{0,100}\b"
            r"(?:english|spanish|french|german|italian|portuguese|dutch|lithuanian|polish)\b|"
            r"\b(?:english|spanish|french|german|italian|portuguese|dutch|lithuanian|polish)\b"
            r".{0,100}\b(?:required|mandatory|must|fluency|fluent|proficiency|written|spoken)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "clearance",
        re.compile(
            r"\b(?:security clearance|clearance required|NATO SECRET|EU SECRET|SC cleared|DV cleared)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "work_authorization",
        re.compile(
            r"\b(?:must be authorized to work|right to work|required work authorization|"
            r"no visa sponsorship|citizenship required|must be a citizen|residency required)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "certification",
        re.compile(
            r"\b(?:certification required|required certification|must hold|must be certified|"
            r"ITIL certification required|CCNA required|Security\+ required)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "experience",
        re.compile(
            r"\b(?:minimum|at least|must have|requires?)\s+\d+\+?\s+years?\b|"
            r"\b\d+\+\s+years?\s+(?:of\s+)?experience\b",
            re.IGNORECASE,
        ),
    ),
    (
        "schedule",
        re.compile(
            r"\b(?:must be available|required to work|availability required)\b.{0,80}"
            r"\b(?:night|weekend|rotating|shift|on[- ]call)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
]


def _database_path() -> Path:
    configured = os.getenv("JOLT_DATABASE_URL", "").strip()
    if configured:
        parsed = urlparse(configured)
        if parsed.scheme != "sqlite":
            raise SystemExit("This read-only audit currently supports SQLite only.")
        raw = unquote(parsed.path)
        if os.name == "nt" and raw.startswith("/") and len(raw) > 2:
            raw = raw[1:]
        return Path(raw)
    return Path(__file__).resolve().parents[1] / "backend" / "data" / "jolt.db"


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _snippet(text: str, match: re.Match[str], radius: int = 180) -> str:
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return " ".join(text[start:end].split())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only audit of historical positive AI reviews for explicit hardline signals "
            "that may have been missed by earlier review contracts."
        )
    )
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--max-jobs", type=int, default=100)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--include-posting-id",
        action="append",
        default=[],
        help="Force a posting into the audit output.",
    )
    args = parser.parse_args()

    path = _database_path().resolve()
    if not path.exists():
        raise SystemExit(f"JOLT database not found: {path}")

    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT
            ar.id AS ai_review_id,
            ar.capture_run_id,
            ar.posting_id,
            ar.source_job_id,
            ar.decision,
            ar.technical_fit,
            ar.hardline_status,
            ar.language_status,
            ar.clearance_status,
            ar.geography_status,
            ar.reviewed_at,
            p.title,
            p.company,
            p.location,
            p.canonical_url,
            sd.source_url,
            sd.raw_text
        FROM ai_reviews ar
        JOIN postings p ON p.id = ar.posting_id
        JOIN source_documents sd ON sd.id = p.source_document_id
        WHERE ar.decision IN ('pursue', 'strong_pursue')
        ORDER BY ar.reviewed_at DESC
        """
    ).fetchall()
    con.close()

    cutoff = datetime.now(UTC) - timedelta(days=max(0, args.days))
    forced = {str(v).strip() for v in args.include_posting_id if str(v).strip()}
    findings: list[dict[str, object]] = []

    for row in rows:
        reviewed_at = _parse_timestamp(str(row["reviewed_at"] or ""))
        if reviewed_at is not None and reviewed_at < cutoff and row["posting_id"] not in forced:
            continue

        text = str(row["raw_text"] or "")
        signals: list[dict[str, str]] = []
        for category, pattern in _PATTERNS:
            match = pattern.search(text)
            if match is not None:
                signals.append(
                    {
                        "category": category,
                        "evidence_snippet": _snippet(text, match),
                    }
                )

        if not signals and row["posting_id"] not in forced:
            continue

        findings.append(
            {
                "ai_review_id": row["ai_review_id"],
                "capture_run_id": row["capture_run_id"],
                "posting_id": row["posting_id"],
                "source_job_id": row["source_job_id"],
                "title": row["title"],
                "company": row["company"],
                "location": row["location"],
                "decision": row["decision"],
                "technical_fit": row["technical_fit"],
                "hardline_status": row["hardline_status"],
                "language_status": row["language_status"],
                "clearance_status": row["clearance_status"],
                "geography_status": row["geography_status"],
                "reviewed_at": str(row["reviewed_at"] or ""),
                "source_url": row["source_url"] or row["canonical_url"],
                "source_text": text,
                "signals": signals,
                "audit_note": (
                    "Pattern match only. Human/AI revalidation must determine whether the requirement "
                    "is mandatory, whether candidate evidence satisfies it, and whether the final "
                    "resolution is preserve, hold, or reject."
                ),
            }
        )

    findings.sort(
        key=lambda item: (
            0 if str(item["posting_id"]) in forced else 1,
            -len(item["signals"]),
            str(item["reviewed_at"]),
        )
    )
    findings = findings[: max(1, args.max_jobs)]

    payload = {
        "pack_type": "jolt_historical_hardline_audit",
        "pack_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "database_read_only": True,
        "window_days": args.days,
        "finding_count": len(findings),
        "forced_posting_ids": sorted(forced),
        "hardline_categories": [
            "language",
            "clearance",
            "work_authorization",
            "certification",
            "experience",
            "schedule",
        ],
        "jobs": findings,
    }

    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output is not None:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(json.dumps({"output": str(output), "finding_count": len(findings)}, indent=2))
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
