"""Read-only quality audit of supervised Jobgether batch reports."""

from __future__ import annotations

import json
from pathlib import Path

from jolt.jobgether_preview import jobgether_identity


def audit_batch(batch: dict, previous: list[dict]) -> dict[str, object]:
    """Audit only canonical identities; prior reports are evidence, not verified jobs."""
    prior_ids: set[str] = set()
    for report in previous:
        for offer in report.get("offers", []):
            if not isinstance(offer, dict):
                continue
            url = offer.get("url")
            identifier = offer.get("source_job_id")
            if (
                isinstance(url, str)
                and isinstance(identifier, str)
                and jobgether_identity(url) == identifier
            ):
                prior_ids.add(identifier)

    structured_ids: dict[str, set[str]] = {}
    for offer in batch.get("offers", []):
        if not isinstance(offer, dict):
            continue
        structured = offer.get("structured_identifier")
        source = offer.get("source_job_id")
        if isinstance(structured, str) and structured and isinstance(source, str):
            structured_ids.setdefault(structured, set()).add(source)

    rows: list[dict[str, object]] = []
    for offer in batch.get("offers", []):
        if not isinstance(offer, dict):
            continue
        url = offer.get("url")
        identifier = offer.get("source_job_id")
        reliable = (
            isinstance(url, str)
            and isinstance(identifier, str)
            and jobgether_identity(url) == identifier
        )
        warnings: list[str] = []
        if not reliable:
            warnings.append("identity_unresolved")
        if offer.get("status") != "extracted_unverified":
            warnings.append("extraction_unresolved")
        countries = offer.get("applicant_countries")
        if isinstance(countries, list) and len(countries) > 100:
            warnings.append("overbroad_country_metadata")
        if not offer.get("spain_declared"):
            warnings.append("spain_not_declared")
        structured = offer.get("structured_identifier")
        if isinstance(structured, str) and len(structured_ids.get(structured, set())) > 1:
            warnings.append("shared_structured_identifier")
        rows.append(
            {
                "source_job_id": identifier,
                "history_status": (
                    "identity_unresolved"
                    if not reliable
                    else "seen_in_previous_report"
                    if identifier in prior_ids
                    else "not_seen_in_available_reports"
                ),
                "warnings": warnings,
                "source_evidence_verified": False,
                "work_from_spain_verified": False,
            }
        )
    return {
        "read_only": True,
        "history_report_count": len(previous),
        "audited_count": len(rows),
        "seen_in_previous_reports": sum(
            row["history_status"] == "seen_in_previous_report" for row in rows
        ),
        "not_seen_in_available_reports": sum(
            row["history_status"] == "not_seen_in_available_reports" for row in rows
        ),
        "jobs": rows,
    }


def load_previous_reports(directory: Path, *, current_output: Path | None = None) -> list[dict]:
    """Read matching JSON reports; ignore corrupt/nonmatching files."""
    reports: list[dict] = []
    if not directory.is_dir():
        return reports
    for file in sorted(directory.glob("JOLT_JOBGETHER_BATCH_*.json")):
        if current_output is not None and file.resolve() == current_output.resolve():
            continue
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            continue
        if (
            isinstance(payload, dict)
            and payload.get("source") == "jobgether"
            and isinstance(payload.get("offers"), list)
        ):
            reports.append(payload)
    return reports
