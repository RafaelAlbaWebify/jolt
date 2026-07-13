from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

API_BASE = "http://127.0.0.1:8000"
APP_URL = "http://127.0.0.1:5173"
EXPECTED_PROFILE = "rafael-job-search:v2"
EXPECTED_ENGINE = "profile-rules-v2"
REQUIRED_REVIEW_FIELDS = {
    "proposed_decision",
    "fit_summary",
    "strengths",
    "gaps",
    "blockers",
    "uncertainties",
    "dimensions",
}


def _get_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=15) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def audit(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    health = _get_json(f"{API_BASE}/api/health")
    opportunities = _get_json(f"{API_BASE}/api/opportunities")
    captures = _get_json(f"{API_BASE}/api/captures")

    if not isinstance(opportunities, list):
        raise RuntimeError("Opportunity API did not return a list.")

    findings: list[dict[str, str]] = []
    for item in opportunities:
        if not isinstance(item, dict):
            findings.append({"severity": "error", "message": "Non-object opportunity returned."})
            continue
        title = str(item.get("title") or "Untitled opportunity")
        missing = sorted(field for field in REQUIRED_REVIEW_FIELDS if field not in item)
        if missing:
            findings.append(
                {
                    "severity": "error",
                    "message": (
                        f"{title}: missing automated-review fields: {', '.join(missing)}"
                    ),
                }
            )
        if item.get("profile_version_id") != EXPECTED_PROFILE:
            findings.append(
                {"severity": "error", "message": f"{title}: unexpected profile version."}
            )
        if item.get("engine_version") != EXPECTED_ENGINE:
            findings.append(
                {"severity": "error", "message": f"{title}: unexpected engine version."}
            )
        score = item.get("ranking_score")
        if not isinstance(score, int) or not 0 <= score <= 100:
            findings.append(
                {"severity": "error", "message": f"{title}: invalid ranking score."}
            )
        if item.get("review_decision") and item.get("proposed_decision") != item.get(
            "review_decision"
        ):
            findings.append(
                {
                    "severity": "info",
                    "message": f"{title}: human decision overrides the automated proposal.",
                }
            )
        if not item.get("fit_summary"):
            findings.append({"severity": "warning", "message": f"{title}: empty fit summary."})
        if not item.get("strengths") and not item.get("gaps"):
            findings.append(
                {"severity": "warning", "message": f"{title}: no strengths or gaps recorded."}
            )

    (output_dir / "health.json").write_text(
        json.dumps(health, indent=2), encoding="utf-8"
    )
    (output_dir / "opportunities.json").write_text(
        json.dumps(opportunities, indent=2), encoding="utf-8"
    )
    (output_dir / "captures.json").write_text(
        json.dumps(captures, indent=2), encoding="utf-8"
    )

    console_messages: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.on(
            "console",
            lambda message: console_messages.append(f"{message.type}: {message.text}"),
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)
        page.screenshot(path=output_dir / "workbench-full.png", full_page=True)
        html = page.locator("body").inner_text()
        (output_dir / "workbench-visible-text.txt").write_text(html, encoding="utf-8")
        browser.close()

    if page_errors:
        findings.extend(
            {"severity": "error", "message": f"Browser error: {error}"}
            for error in page_errors
        )
    automated_review_visible = "Automated proposed decision" in html
    if opportunities and not automated_review_visible:
        findings.append(
            {
                "severity": "error",
                "message": "Automated review data exists but is not visible in the workbench.",
            }
        )

    summary: dict[str, object] = {
        "status": "failed"
        if any(item["severity"] == "error" for item in findings)
        else "passed",
        "opportunity_count": len(opportunities),
        "capture_count": len(captures) if isinstance(captures, list) else None,
        "automated_review_visible": automated_review_visible,
        "findings": findings,
        "console_messages": console_messages,
        "page_errors": page_errors,
    }
    (output_dir / "audit-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    summary = audit(args.output_dir)
    print(json.dumps(summary, indent=2))
    return 1 if summary["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
