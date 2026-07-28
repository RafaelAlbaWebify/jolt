from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

API_BASE = "http://127.0.0.1:8000"
APP_URL = "http://127.0.0.1:5173"
VIEWPORT = {"width": 1680, "height": 945}


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def request_json(method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, Any]:
    data = json.dumps(payload or {}).encode("utf-8") if method != "GET" else None
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            loaded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
    if not isinstance(loaded, dict):
        raise RuntimeError(f"{method} {path} did not return an object")
    return loaded


def create_reviewed_opportunity() -> dict[str, Any]:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    title = f"JOLT Daily Workflow Audit {stamp}"
    raw_text = (
        f"{title}\n"
        "Audit Systems Ltd\n"
        "Location: Remote Spain\n"
        "Application support engineer role involving Windows, Active Directory, SQL "
        "troubleshooting, incident management, APIs, logs, customer support, Microsoft 365, "
        "Azure, VMware, documentation, service management, and production support."
    )
    source_url = f"https://example.test/jolt-daily-workflow/{stamp}"

    intake = request_json(
        "POST",
        "/api/intake/manual",
        {"source_url": source_url, "raw_text": raw_text},
    )
    posting_id = str(intake["posting_id"])
    evaluation_id = str(intake["evaluation_id"])
    review = request_json(
        "POST",
        f"/api/opportunities/{posting_id}/reviews",
        {
            "evaluation_id": evaluation_id,
            "decision": "pursue",
            "notes": "Daily workflow audit pursue decision.",
        },
    )

    assert_true(posting_id, "Manual intake did not create a posting")
    assert_true(review.get("decision") == "pursue", "Pursue review was not recorded")

    return {
        "fixture_title": title,
        "posting_id": posting_id,
        "evaluation_id": evaluation_id,
        "review": review,
    }


def complete_application_vertical_slice(opportunity: dict[str, Any]) -> dict[str, Any]:
    posting_id = str(opportunity["posting_id"])
    application = request_json(
        "POST",
        f"/api/opportunities/{posting_id}/applications",
        {
            "application_url": "https://example.test/apply",
            "resume_used": "JOLT audit resume",
            "notes": "Daily workflow audit application record.",
        },
    )
    application_id = str(application["application_id"])

    submitted = request_json(
        "POST",
        f"/api/applications/{application_id}/transitions",
        {"status": "submitted", "notes": "Audit submitted externally."},
    )
    recruiter_screen = request_json(
        "POST",
        f"/api/applications/{application_id}/transitions",
        {"status": "recruiter_screen", "notes": "Audit recruiter screen scheduled."},
    )
    corrected = request_json(
        "POST",
        f"/api/applications/{application_id}/transitions",
        {"status": "preparing", "notes": "Audit correction back to preparing."},
    )

    task = request_json(
        "POST",
        f"/api/applications/{application_id}/tasks",
        {
            "title": "Audit follow-up task",
            "notes": "Created by daily workflow audit.",
            "due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    completed_task = request_json("POST", f"/api/application-tasks/{task['task_id']}/complete")

    interview = request_json(
        "POST",
        f"/api/applications/{application_id}/interviews",
        {
            "interview_type": "recruiter_screen",
            "scheduled_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "timezone": "Europe/Madrid",
            "format_location": "Video call",
            "participants": "Audit recruiter",
            "preparation_notes": "Daily workflow audit interview.",
        },
    )

    outcome = request_json(
        "POST",
        f"/api/applications/{application_id}/outcomes",
        {
            "outcome_type": "no_response",
            "reason_code": "audit_no_response",
            "notes": "Daily workflow audit outcome.",
        },
    )
    reopened = request_json(
        "POST",
        f"/api/applications/{application_id}/transitions",
        {"status": "preparing", "notes": "Audit reopen after outcome changed."},
    )
    reloaded = request_json("GET", f"/api/applications/{application_id}")

    events = reloaded.get("events", [])
    assert_true(application.get("status") == "preparing", "Application did not start in preparing")
    assert_true(submitted.get("status") == "submitted", "Application did not move to submitted")
    assert_true(
        recruiter_screen.get("status") == "recruiter_screen",
        "Application did not move to recruiter screen",
    )
    assert_true(corrected.get("status") == "preparing", "Backward correction to preparing failed")
    assert_true(completed_task.get("status") == "completed", "Task completion failed")
    assert_true(interview.get("status") == "scheduled", "Interview creation failed")
    assert_true(outcome.get("outcome_type") == "no_response", "Outcome was not recorded")
    assert_true(reopened.get("status") == "preparing", "Application reopen failed")
    assert_true(len(events) >= 8, f"Expected a dense timeline, got {len(events)} events")
    assert_true(
        any(event.get("event_type") == "application_reopened" for event in events),
        "Reopen event was not preserved in the timeline",
    )
    assert_true(
        any("Previous outcome: no_response" in event.get("notes", "") for event in events),
        "Reopen timeline did not preserve the previous outcome details",
    )

    return {
        **opportunity,
        "application_id": application_id,
        "application_created": application,
        "submitted": submitted,
        "recruiter_screen": recruiter_screen,
        "corrected": corrected,
        "task": task,
        "completed_task": completed_task,
        "interview": interview,
        "outcome": outcome,
        "reopened": reopened,
        "reloaded": reloaded,
    }


def wait_for_fixture(page: Page, section_name: str, fixture_title: str) -> None:
    page.get_by_role("button", name=section_name, exact=True).click()
    page.get_by_text(fixture_title, exact=True).wait_for(timeout=30_000)


def audit(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    api_summary = create_reviewed_opportunity()
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "requestfailed",
            lambda request: failed_requests.append(
                f"{request.method} {request.url}: {request.failure}"
            ),
        )
        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)
        wait_for_fixture(page, "Opportunities", api_summary["fixture_title"])
        page.screenshot(path=output_dir / "daily-workflow-opportunities.png", full_page=True)

        api_summary = complete_application_vertical_slice(api_summary)
        wait_for_fixture(page, "Applications", api_summary["fixture_title"])
        page.screenshot(path=output_dir / "daily-workflow-applications.png", full_page=True)
        browser.close()

    summary = {
        "api_vertical_slice": api_summary,
        "viewport": VIEWPORT,
        "opportunities_screenshot": "daily-workflow-opportunities.png",
        "applications_screenshot": "daily-workflow-applications.png",
        "console_errors": console_errors,
        "page_errors": page_errors,
        "failed_requests": failed_requests,
    }
    (output_dir / "daily-workflow-audit-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    assert_true(not console_errors, f"Browser console errors: {console_errors}")
    assert_true(not page_errors, f"Page errors: {page_errors}")
    assert_true(not failed_requests, f"Failed browser requests: {failed_requests}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
