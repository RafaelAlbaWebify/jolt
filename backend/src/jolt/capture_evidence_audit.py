from __future__ import annotations

from collections.abc import Callable
from typing import Any

Finding = dict[str, str]
CaptureDetailFetcher = Callable[[str], object]


def audit_capture_evidence(
    captures: object,
    fetch_detail: CaptureDetailFetcher,
) -> tuple[dict[str, object], list[Finding], dict[str, int]]:
    details: dict[str, object] = {}
    findings: list[Finding] = []
    metrics = {
        "capture_detail_count": 0,
        "capture_item_count": 0,
        "capture_artifact_count": 0,
        "legacy_capture_item_count": 0,
    }

    if not isinstance(captures, list):
        findings.append({"severity": "error", "message": "Capture API did not return a list."})
        return details, findings, metrics

    for summary in captures:
        if not isinstance(summary, dict):
            findings.append({"severity": "error", "message": "Capture history contains a non-object row."})
            continue

        run_id = str(summary.get("capture_run_id") or "")
        if not run_id:
            findings.append({"severity": "error", "message": "Capture history row is missing capture_run_id."})
            continue

        try:
            detail = fetch_detail(run_id)
            details[run_id] = detail
            if not isinstance(detail, dict):
                raise RuntimeError("detail endpoint did not return an object")

            metrics["capture_detail_count"] += 1
            _validate_summary_consistency(summary, detail, findings, run_id)
            _validate_run_metadata(detail, findings, run_id)
            _validate_items(detail, findings, metrics, run_id)
        except Exception as exc:  # noqa: BLE001
            findings.append(
                {
                    "severity": "error",
                    "message": f"Capture {run_id}: detail audit failed: {exc}",
                }
            )

    return details, findings, metrics


def _validate_summary_consistency(
    summary: dict[str, Any],
    detail: dict[str, Any],
    findings: list[Finding],
    run_id: str,
) -> None:
    detail_summary = {key: value for key, value in detail.items() if key not in {"pages", "items"}}
    if detail_summary != summary:
        findings.append(
            {
                "severity": "error",
                "message": f"Capture {run_id}: summary and detail metadata differ.",
            }
        )


def _validate_run_metadata(
    detail: dict[str, Any],
    findings: list[Finding],
    run_id: str,
) -> None:
    observed = detail.get("observed_item_count")
    total = detail.get("total_items")
    verified = detail.get("verified_items")
    rejected = detail.get("rejected_items")
    requested = detail.get("requested_item_limit")
    stop_reason = detail.get("stop_reason")

    for name, value in {
        "observed_item_count": observed,
        "total_items": total,
        "verified_items": verified,
        "rejected_items": rejected,
    }.items():
        if not isinstance(value, int) or value < 0:
            findings.append(
                {
                    "severity": "error",
                    "message": f"Capture {run_id}: invalid {name}.",
                }
            )

    if all(isinstance(value, int) for value in (total, verified, rejected)) and total != verified + rejected:
        findings.append(
            {
                "severity": "error",
                "message": f"Capture {run_id}: verified and rejected counts do not equal total items.",
            }
        )

    if isinstance(observed, int) and isinstance(total, int) and observed != total:
        findings.append(
            {
                "severity": "error",
                "message": f"Capture {run_id}: observed count does not equal persisted item count.",
            }
        )

    if requested is not None and (not isinstance(requested, int) or requested < 1):
        findings.append(
            {
                "severity": "error",
                "message": f"Capture {run_id}: requested item limit is invalid.",
            }
        )
    if isinstance(requested, int) and isinstance(observed, int) and observed > requested:
        findings.append(
            {
                "severity": "error",
                "message": f"Capture {run_id}: observed count exceeds requested limit.",
            }
        )
    if not isinstance(stop_reason, str) or not stop_reason:
        findings.append(
            {
                "severity": "error",
                "message": f"Capture {run_id}: stop reason is missing.",
            }
        )


def _validate_items(
    detail: dict[str, Any],
    findings: list[Finding],
    metrics: dict[str, int],
    run_id: str,
) -> None:
    items = detail.get("items")
    if not isinstance(items, list):
        findings.append({"severity": "error", "message": f"Capture {run_id}: items are missing."})
        return

    metrics["capture_item_count"] += len(items)
    for item in items:
        if not isinstance(item, dict):
            findings.append(
                {"severity": "error", "message": f"Capture {run_id}: non-object capture item."}
            )
            continue

        job_id = str(item.get("source_job_id") or "unknown")
        status = item.get("detail_status")
        posting_id = item.get("posting_id")
        source_document_id = item.get("source_document_id")
        artifact_id = item.get("artifact_id")
        artifact_hash = item.get("artifact_hash")

        if status == "verified":
            if not posting_id or not source_document_id:
                findings.append(
                    {
                        "severity": "error",
                        "message": f"Capture {run_id}/{job_id}: verified item lacks canonical linkage.",
                    }
                )
        elif status == "rejected_unverified":
            if posting_id or source_document_id:
                findings.append(
                    {
                        "severity": "error",
                        "message": f"Capture {run_id}/{job_id}: rejected item has canonical linkage.",
                    }
                )
        else:
            findings.append(
                {
                    "severity": "error",
                    "message": f"Capture {run_id}/{job_id}: unexpected detail status.",
                }
            )

        if artifact_id is None and artifact_hash is None:
            metrics["legacy_capture_item_count"] += 1
            continue
        if not artifact_id or not isinstance(artifact_hash, str) or len(artifact_hash) != 64:
            findings.append(
                {
                    "severity": "error",
                    "message": f"Capture {run_id}/{job_id}: incomplete artifact identity or hash.",
                }
            )
            continue
        try:
            int(artifact_hash, 16)
        except ValueError:
            findings.append(
                {
                    "severity": "error",
                    "message": f"Capture {run_id}/{job_id}: artifact hash is not hexadecimal SHA-256.",
                }
            )
            continue
        metrics["capture_artifact_count"] += 1
