"""Read-only live acceptance of source details in the JOLT Review Inbox.

Never creates/updates Postings, AI decisions or Applications.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


def fetch_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=15) as response:  # noqa: S310
        return json.load(response)


def check_opportunity(
    api_base: str, company: str, title: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    opportunities = fetch_json(f"{api_base}/api/ai-review/opportunity-index")
    if not isinstance(opportunities, list):
        raise ValueError("Review index is not a list")
    candidates = [
        item for item in opportunities
        if isinstance(item, dict)
        and str(item.get("company", "")).strip().casefold() == company.casefold()
        and str(item.get("title", "")).strip().casefold() == title.casefold()
    ]
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one matching opportunity, got {len(candidates)}")
    posting = candidates[0]
    detail = fetch_json(
        f"{api_base}/api/opportunities/{posting['posting_id']}/source-description"
    )
    if not isinstance(detail, dict) or not isinstance(detail.get("description"), str):
        raise ValueError("Source-description API returned no description")
    if len(detail["description"].strip()) < 150:
        raise ValueError("Source description is absent or implausibly short")
    return posting, detail


def run_audit(
    api_base: str, app_url: str, company: str, title: str, output: Path
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    posting, detail = check_opportunity(api_base.rstrip("/"), company, title)
    failures: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            page.goto(app_url, wait_until="domcontentloaded", timeout=30000)
            page.get_by_role("button", name="Review Inbox", exact=True).click()
            page.get_by_placeholder("Search inbox").fill(company)
            page.get_by_text(title, exact=True).first.wait_for(timeout=15000)
            page.get_by_role("button", name="Inspect full details").click()
            dialog = page.get_by_role("dialog", name=title)
            dialog.wait_for(timeout=15000)
            section = dialog.get_by_role("region", name="Captured job description")
            section.wait_for(timeout=15000)
            expected = " ".join(detail["description"].split())
            actual = " ".join(section.inner_text().split())
            if expected not in actual:
                failures.append("Visible inspector description differs from persisted Posting.description")
            if not dialog.get_by_text("AI review required before deciding.").count() and not posting.get("ai_review_id"):
                failures.append("Pending job is missing the AI-review decision gate")
            page.screenshot(path=str(output / "review-inspector.png"), full_page=True)
        finally:
            browser.close()
    result = {
        "timestamp": datetime.now(UTC).isoformat(),
        "source": str(posting.get("source_url") or ""),
        "posting_id": posting["posting_id"],
        "company": company,
        "title": title,
        "description_length": len(detail["description"]),
        "pass": not failures,
        "findings": failures,
        "read_only": True,
        "screenshot": str(output / "review-inspector.png"),
    }
    (output / "review-inspector-acceptance.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--app", default="http://127.0.0.1:5173")
    parser.add_argument("--company", default="thinkbridge")
    parser.add_argument("--title", default="Support Engineer")
    parser.add_argument("--output", type=Path, default=Path.home() / "Downloads" / "JOLT_REVIEW_INSPECTOR_AUDIT")
    args = parser.parse_args()
    result = run_audit(args.api, args.app, args.company, args.title, args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
