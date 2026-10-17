"""Read-only browser acceptance of the running local JOLT application."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

API = "http://127.0.0.1:8000"
APP = "http://127.0.0.1:5173"
SECTIONS = ("Capture Jobs", "Review Inbox", "Applications", "Market Insights")


def fetch(path):
    with urlopen(API + path, timeout=15) as response:  # noqa: S310
        return json.loads(response.read())


def accept(destination):
    destination.mkdir(parents=True, exist_ok=True)
    errors = []
    screenshots = {}
    health = fetch("/api/health")
    records = fetch("/api/opportunity-index")
    if not isinstance(records, list):
        raise RuntimeError("Opportunity index was not a list")
    observations = []
    for record in records[:5]:
        pid = record["posting_id"]
        source = fetch(f"/api/discovery-postings/{pid}/source-history")
        observations.append(
            {
                "posting_id": pid,
                "source_count": len(source["sources"]),
                "observations": source["total_observations"],
                "confirmed_duplicates": len(source["confirmed_duplicates"]),
            }
        )
    blocked = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})

        def read_only(route):
            if route.request.method not in ("GET", "HEAD", "OPTIONS"):
                blocked.append(route.request.method)
                route.abort()
            else:
                route.continue_()

        context.route("**/*", read_only)
        page = context.new_page()
        try:
            page.goto(APP, wait_until="domcontentloaded")
            for label in SECTIONS:
                try:
                    page.get_by_role("button", name=label, exact=True).first.click()
                    page.wait_for_timeout(700)
                    filename = label.lower().replace(" ", "-") + ".png"
                    page.screenshot(path=str(destination / filename), full_page=True)
                    screenshots[label] = filename
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{label}: {exc}")
        finally:
            browser.close()
    if blocked:
        errors.append(f"Browser attempted {len(blocked)} blocked mutations")
    return {
        "schema": "jolt-read-only-operator-acceptance-v1",
        "generated_utc": datetime.now(UTC).isoformat(),
        "health": health,
        "opportunity_count": len(records),
        "provenance_samples": observations,
        "screenshots": screenshots,
        "blocked_mutation_count": len(blocked),
        "errors": errors,
        "result": "PASS" if not errors else "FAIL",
        "limitations": [
            "No live captures, AI imports, or human decisions performed",
            "Read-only browser and five-record provenance sample only",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = accept(args.output_dir)
    except Exception as exc:  # noqa: BLE001
        result = {"result": "FAIL", "errors": [str(exc)]}
    (args.output_dir / "acceptance.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(result["result"])
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
