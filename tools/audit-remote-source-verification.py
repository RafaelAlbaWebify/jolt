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
    r"\b(?:fully\s+remote|100%\s+remote|work\s+from\s+anywhere|"
    r"remote[- ]first|remote\s+(?:role|position|job)|(?:role|position|job)\s+is\s+remote|"
    r"this\s+is\s+(?:a\s+)?remote\s+(?:role|position|job)|work(?:ing)?\s+remotely|"
    r"location\s*:\s*remote|teletrabajo)\b",
    re.IGNORECASE,
)
_REVIEW_DECISIONS = {"strong_pursue", "pursue", "conditional"}
_POSITIVE_DECISIONS = {"strong_pursue", "pursue"}
_OFFICIAL_AUTHORITIES = {"official_ats", "official_careers", "company_site"}
_LOCAL_GALICIA = re.compile(r"\b(?:vigo|pontevedra|galicia)\b", re.IGNORECASE)


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
    parser.add_argument(
        "--match",
        default="",
        help="Optional case-insensitive title/company/location filter.",
    )
    parser.add_argument(
        "--revalidation-pack",
        type=Path,
        default=None,
        help=(
            "Write a focused JSON pack for source revalidation instead of printing the full audit. "
            "The pack includes positive historical reviews, prioritizes explicit Remote signals, and "
            "keeps source evidence needed for an AI review 1.2 correction."
        ),
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=25,
        help="Maximum jobs in --revalidation-pack output (default: 25).",
    )
    parser.add_argument(
        "--include-posting-id",
        action="append",
        default=[],
        help="Force a posting_id into the revalidation pack even if it falls below the normal risk cut.",
    )
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
            ar.capture_run_id,
            ar.posting_id,
            ar.source_job_id,
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
        location_text = str(row["location"] or "")
        remote_signal = bool(re.search(r"\(Remote\)|\bRemote\b", location_text, re.IGNORECASE)) or bool(
            _REMOTE_SIGNAL.search(raw_text)
        )
        decision = str(row["decision"] or "")
        verification = str(row["location_verification_status"] or "unverified")
        conflict = bool(row["source_conflict"])

        authority = str(row["authoritative_source"] or "")
        location = str(row["location"] or "")
        verified_geography = verification == "verified" and not conflict
        local_non_remote = bool(_LOCAL_GALICIA.search(location)) and not remote_signal

        needs_revalidation = (
            decision in _REVIEW_DECISIONS
            and (
                conflict
                or (
                    remote_signal
                    and (
                        authority not in _OFFICIAL_AUTHORITIES
                        or str(row["remote_status"] or "") != "confirmed_remote"
                        or verification != "verified"
                    )
                )
                or (
                    not remote_signal
                    and not verified_geography
                    and not local_non_remote
                )
            )
        )
        if not needs_revalidation:
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
                "decision": decision,
                "geography_status": row["geography_status"],
                "location_eligibility": row["location_eligibility"],
                "technical_fit": row["technical_fit"],
                "linkedin_source_url": row["source_url"] or row["canonical_url"],
                "source_text": raw_text,
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

    if args.revalidation_pack is not None:
        forced = {str(value).strip() for value in args.include_posting_id if str(value).strip()}

        def risk_key(item: dict[str, object]) -> tuple[int, str, str]:
            posting_id = str(item.get("posting_id") or "")
            decision = str(item.get("decision") or "")
            remote_signal = bool(item.get("text_remote_signal"))
            location = str(item.get("location") or "")
            authority = str(item.get("authoritative_source") or "")
            verification = str(item.get("location_verification_status") or "")
            conflict = bool(item.get("source_conflict"))

            if posting_id in forced:
                level = 0
            elif conflict:
                level = 1
            elif decision in _POSITIVE_DECISIONS and remote_signal:
                level = 2
            elif (
                decision in _POSITIVE_DECISIONS
                and authority not in _OFFICIAL_AUTHORITIES
                and verification != "verified"
                and not _LOCAL_GALICIA.search(location)
            ):
                level = 3
            elif decision in _POSITIVE_DECISIONS:
                level = 4
            else:
                level = 9

            reviewed_at = str(item.get("reviewed_at") or "")
            return (level, reviewed_at, posting_id)

        candidates = [
            item
            for item in findings
            if str(item.get("decision") or "") in _POSITIVE_DECISIONS
            or str(item.get("posting_id") or "") in forced
        ]
        candidates.sort(key=risk_key)

        max_jobs = max(1, args.max_jobs)
        selected = candidates[:max_jobs]
        selected_ids = {str(item["posting_id"]) for item in selected}

        # A forced posting must never disappear because of the max limit.
        for item in candidates[max_jobs:]:
            posting_id = str(item["posting_id"])
            if posting_id in forced and posting_id not in selected_ids:
                selected.append(item)
                selected_ids.add(posting_id)

        jobs: list[dict[str, object]] = []
        for position, item in enumerate(selected, start=1):
            jobs.append(
                {
                    "position": position,
                    "risk_tier": risk_key(item)[0],
                    "capture_run_id": item["capture_run_id"],
                    "ai_review_id": item["ai_review_id"],
                    "posting_id": item["posting_id"],
                    "source_job_id": item["source_job_id"],
                    "title": item["title"],
                    "company": item["company"],
                    "location": item["location"],
                    "linkedin_source_url": item["linkedin_source_url"],
                    "source_text": item["source_text"],
                    "previous_review": {
                        "decision": item["decision"],
                        "geography_status": item["geography_status"],
                        "location_eligibility": item["location_eligibility"],
                        "technical_fit": item["technical_fit"],
                        "reviewed_at": item["reviewed_at"],
                    },
                    "source_verification_before_revalidation": {
                        "source_conflict": item["source_conflict"],
                        "linkedin_work_model": item["linkedin_work_model"],
                        "official_work_model": item["official_work_model"],
                        "authoritative_source": item["authoritative_source"],
                        "official_source_url": item["official_source_url"],
                        "remote_status": item["remote_status"],
                        "location_verification_status": item[
                            "location_verification_status"
                        ],
                        "source_confidence": item["source_confidence"],
                    },
                }
            )

        pack = {
            "pack_type": "jolt_source_revalidation_input",
            "pack_version": "1.0",
            "ai_review_contract_version": "1.2",
            "generated_at": datetime.now(UTC).isoformat(),
            "database_read_only": True,
            "selection": {
                "window_days": args.days,
                "audit_findings": len(findings),
                "positive_candidates": len(candidates),
                "selected_jobs": len(jobs),
                "max_jobs": max_jobs,
                "forced_posting_ids": sorted(forced),
                "risk_tiers": {
                    "0": "explicitly forced into this pack",
                    "1": "existing source conflict",
                    "2": "positive decision plus explicit Remote signal",
                    "3": "positive decision, non-local location, no authoritative verification",
                    "4": "other positive historical review lacking authoritative verification",
                },
            },
            "workflow": [
                "Treat LinkedIn only as discovery evidence.",
                "Locate the employer-controlled ATS/careers/company job page when available.",
                "Verify work model, hiring geography, and cross-border/work-authorization constraints.",
                "Record both LinkedIn and official work models separately.",
                "If sources diverge, official employer-controlled evidence has priority and source_conflict must be true.",
                "A LinkedIn Remote label alone cannot produce confirmed_remote or a positive final decision.",
                "Do not force SKIP_BY_LOCATION when flexibility remains genuinely unresolved; use conditional/HOLD-VERIFY.",
                "Return AI review 1.2 corrections grouped by capture_run_id so they can be imported through /api/ai-review/import.",
            ],
            "jobs": jobs,
            "return_contract": {
                "type": "array_of_jolt_ai_review_imports",
                "group_by": "capture_run_id",
                "contract_type": "jolt_ai_review",
                "contract_version": "1.2",
                "review_source": "chatgpt_source_first",
                "required_source_fields": [
                    "source_conflict",
                    "linkedin_work_model",
                    "official_work_model",
                    "authoritative_source",
                    "official_source_url",
                    "remote_status",
                    "location_verification_status",
                    "source_confidence",
                ],
            },
        }

        output_path = args.revalidation_pack.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(pack, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "output": str(output_path),
                    "selected_jobs": len(jobs),
                    "audit_findings": len(findings),
                    "positive_candidates": len(candidates),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

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
