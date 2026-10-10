"""Summarize sequential Indeed capture ZIPs without exposing descriptions."""

from __future__ import annotations

import argparse
import json
import statistics
import zipfile
from pathlib import Path


def analyze(directory: Path) -> dict[str, object]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8-sig"))
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for run in manifest:
        item: dict[str, object] = {
            "search": run["search"],
            "status": run["status"],
            "error": run.get("error", ""),
            "captured": 0,
            "verified": 0,
            "first_seen_in_benchmark": 0,
            "already_seen_in_benchmark": 0,
            "new_postings": 0,
            "known_postings": 0,
            "mean_seconds": None,
            "pages_visited": 0,
            "elapsed_seconds": None,
            "unique_verified_known_ids": 0,
            "sponsored_label_detected": 0,
            "displayed_age_detected": 0,
        }
        if run.get("archive"):
            with zipfile.ZipFile(directory / run["archive"]) as archive:
                capture = json.loads(archive.read("capture_summary.json"))
                response = json.loads(archive.read("api_result.json"))
            cards = capture.get("cards", [])
            ids = [str(card["source_job_id"]) for card in cards]
            unique = set(ids)
            item["captured"] = len(cards)
            item["verified"] = capture.get("verified_count", 0)
            item["pages_visited"] = capture.get("pages_visited", 0)
            item["elapsed_seconds"] = capture.get("elapsed_seconds")
            item["unique_verified_known_ids"] = capture.get("unique_verified_known_ids", 0)
            item["identical_page_count"] = sum(
                bool(page.get("identical_to_previous_page")) for page in capture.get("pages", [])
            )
            observed = {}
            for page in capture.get("pages", []):
                observed.update(page.get("listing_signals", {}))
            item["sponsored_label_detected"] = sum(
                bool(observed.get(job_id, {}).get("sponsored_label_detected"))
                for job_id in unique
            )
            item["displayed_age_detected"] = sum(
                bool(observed.get(job_id, {}).get("displayed_age"))
                for job_id in unique
            )

            item["first_seen_in_benchmark"] = len(unique - seen)
            item["already_seen_in_benchmark"] = len(unique & seen)
            item["stop_reason"] = capture.get("stop_reason")
            item["backend_status"] = response.get("status")
            item["warnings"] = len(response.get("warnings", []))
            states = [
                str(value.get("identity_status") or "")
                for value in response.get("items", [])
            ]
            item["identity_status_counts"] = {
                state: states.count(state) for state in sorted(set(states))
            }
            item["new_postings"] = sum(value == "new" for value in states)
            item["known_postings"] = sum(value in {"confirmed_duplicate", "probable_duplicate", "existing_posting_update"} for value in states)
            timings = [
                float(value["total_seconds"])
                for value in capture.get("job_timings", [])
                if "total_seconds" in value
            ]
            if timings:
                item["mean_seconds"] = round(statistics.mean(timings), 3)
            seen.update(unique)
        rows.append(item)
    report: dict[str, object] = {
        "source": "indeed",
        "purpose": "sequential search coverage and capture diagnostics",
        "warning": "No relevance judgement or hiring eligibility inferred; identity_status counts are backend labels and should be interpreted with the source schema.",
        "unique_job_ids_across_runs": len(seen),
        "searches": rows,
    }
    (directory / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.directory)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
