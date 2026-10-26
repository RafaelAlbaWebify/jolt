"""Read-only evidence audit of JOLT saved searches; never launches captures.

Usage: python tools/audit-job-search-evidence.py --api-url http://127.0.0.1:8000
Outputs CSV/JSON to Downloads/JOLT_SEARCH_AUDIT_<UTC timestamp>.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen


def get_json(base: str, path: str):
    with urlopen(base + path, timeout=20) as response:
        return json.load(response)


def search_url(portal: str, row: dict) -> str:
    return row.get("definition", {}).get("search_url", "") if portal == "indeed" else row.get("search_url", "")


def inspect_url(portal: str, url: str) -> dict:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    remote = params.get("f_WT", [""])[0] == "2" if portal == "linkedin" else False
    national = (params.get("geoId", [""])[0] == "105646813" if portal == "linkedin"
                else "españa" in params.get("l", [""])[0].casefold())
    warnings = []
    if portal == "indeed" and national:
        warnings.append("national_without_explicit_remote_constraint")
    if portal == "linkedin" and not national and not params.get("distance"):
        warnings.append("local_without_explicit_distance")
    if portal == "linkedin" and national and remote:
        warnings.append("remote_only_excludes_hybrid")
    if portal == "linkedin" and params.get("f_TPR") == ["r604800"]:
        warnings.append("last_seven_days_only")
    return {"scope": "national" if national else "local", "remote_only": remote,
            "warnings": warnings, "criteria": params}


def load_executions(base: str, path: str) -> list[dict]:
    try:
        result = get_json(base, path)
    except Exception as exc:
        print(f"WARNING: cannot read {path}: {exc}")
        return []
    return result if isinstance(result, list) else []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.api_url not in ("http://127.0.0.1:8000", "http://localhost:8000"):
        parser.error("Only local JOLT port 8000 is permitted")
    searches = {
        "indeed": get_json(args.api_url, "/api/discovery-searches?source=indeed"),
        "linkedin": get_json(args.api_url, "/api/linkedin-searches"),
    }
    executions = load_executions(args.api_url, "/api/discovery-executions")
    linkedin_executions = load_executions(args.api_url, "/api/linkedin-discovery-batches")
    by_search: dict[str, list[dict]] = {}
    for row in executions + linkedin_executions:
        if row.get("saved_search_id"):
            by_search.setdefault(row["saved_search_id"], []).append(row)
    rows = []
    for portal, catalog in searches.items():
        for item in catalog:
            if not item.get("enabled"):
                continue
            url = search_url(portal, item)
            flags = inspect_url(portal, url)
            history = sorted(by_search.get(item["id"], []),
                             key=lambda r: r.get("created_at") or r.get("started_at") or "",
                             reverse=True)
            latest = history[0] if history else {}
            counts = Counter(r.get("status", "unknown") for r in history)
            rows.append({
                "portal": portal, "search_id": item["id"], "label": item.get("label", ""),
                "url": url, "scope": flags["scope"],
                "remote_only": flags["remote_only"],
                "configuration_warnings": ";".join(flags["warnings"]),
                "execution_count": len(history), "completed_count": counts["completed"],
                "failed_count": counts["failed"],
                "latest_status": latest.get("status", "no_execution_evidence"),
                "latest_captured_count": latest.get("captured_count", ""),
                "latest_error": latest.get("error", ""),
                "latest_capture_run_id": latest.get("capture_run_id", ""),
                "quality_and_eligibility": "not_measured_in_this_report",
            })
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = args.out or Path.home() / "Downloads" / f"JOLT_SEARCH_AUDIT_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "search_audit.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    if rows:
        with (out / "search_audit.csv").open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    summary = {
        "observed_search_count": len(rows),
        "by_portal": dict(Counter(row["portal"] for row in rows)),
        "warnings_by_type": dict(Counter(w for row in rows for w in
                                         row["configuration_warnings"].split(";") if w)),
        "with_execution_evidence": sum(r["execution_count"] > 0 for r in rows),
        "limit": "Historical outcomes per search are not a measure of eligibility or incremental unique leads; no capture was launched.",
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"REPORT: {out}")


if __name__ == "__main__":
    main()
