from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, Response, sync_playwright

APP_URL = "http://127.0.0.1:5173"
API_URL = "http://127.0.0.1:8000"
VIEWPORT = {"width": 1680, "height": 945}


def record_action(actions: list[dict[str, str]], action: str, result: str) -> None:
    actions.append({"action": action, "result": result})


def api_json(page: Page, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    response = page.request.fetch(
        f"{API_URL}{path}",
        method=method,
        data=payload,
        headers={"Content-Type": "application/json"} if payload is not None else None,
    )
    if not response.ok:
        raise AssertionError(f"{method} {path} returned HTTP {response.status}: {response.text()}")
    return response.json()


def create_fixture(page: Page) -> dict[str, str]:
    stamp = time.strftime("%Y%m%d%H%M%S")
    title = f"JOLT Certification Application {stamp}"
    posting = api_json(
        page,
        "POST",
        "/api/intake/manual",
        {
            "source_url": f"https://example.invalid/jolt-certification-{stamp}",
            "raw_text": (
                f"{title}\n"
                "Example Certification Company\n"
                "Remote, Spain\n"
                "Application Support Engineer responsible for SQL, APIs, SaaS troubleshooting, "
                "incident management, documentation, and customer communication."
            ),
        },
    )
    posting_id = str(posting["posting_id"])
    opportunity = api_json(page, "GET", f"/api/opportunity-detail/{posting_id}")
    api_json(
        page,
        "POST",
        f"/api/opportunities/{posting_id}/reviews",
        {"evaluation_id": opportunity["evaluation_id"], "decision": "pursue"},
    )
    application = api_json(page, "GET", "/api/application-index")
    row = next((item for item in application if item.get("posting_id") == posting_id), None)
    if not row or not row.get("application_id"):
        raise AssertionError("Certification application was not created after pursuing the opportunity.")
    application_id = str(row["application_id"])
    api_json(
        page,
        "POST",
        f"/api/applications/{application_id}/transitions",
        {"status": "submitted", "notes": "Certification fixture moved to Applied."},
    )
    return {"posting_id": posting_id, "application_id": application_id, "title": title}


def viewport_metrics(page: Page, workspace: str) -> dict[str, Any]:
    metrics = page.evaluate(
        """() => {
            const shell = document.querySelector('.workspace-shell');
            const sidebar = document.querySelector('.workspace-sidebar');
            const content = document.querySelector('.workspace-content');
            if (!shell || !sidebar || !content) throw new Error('Workspace structure is incomplete.');
            const shellBox = shell.getBoundingClientRect();
            const sidebarBox = sidebar.getBoundingClientRect();
            const contentBox = content.getBoundingClientRect();
            return {
                shellLeft: shellBox.left,
                shellRight: shellBox.right,
                sidebarRight: sidebarBox.right,
                contentLeft: contentBox.left,
                contentWidth: contentBox.width,
                documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            };
        }"""
    )
    if metrics["shellLeft"] > 24 or metrics["shellRight"] < VIEWPORT["width"] - 24:
        raise AssertionError(f"Workspace shell does not use the viewport in {workspace}: {metrics}")
    if metrics["sidebarRight"] >= metrics["contentLeft"]:
        raise AssertionError(f"Sidebar overlaps content in {workspace}: {metrics}")
    if metrics["contentWidth"] < VIEWPORT["width"] * 0.65:
        raise AssertionError(f"Content is squeezed in {workspace}: {metrics}")
    if metrics["documentOverflow"] > 1:
        raise AssertionError(f"Document-level overflow exists in {workspace}: {metrics}")
    return metrics


def assert_success(response: Response, action: str) -> None:
    if not response.ok:
        raise AssertionError(f"{action} returned HTTP {response.status}: {response.url}")


def click_workspace(page: Page, label: str, heading: str) -> None:
    page.get_by_role("button", name=label, exact=True).click()
    page.get_by_role("heading", name=heading, exact=True).wait_for(timeout=30_000)


def open_application(page: Page, fixture: dict[str, str]) -> None:
    click_workspace(page, "Applications", "Application Pipeline")
    card = page.locator(f'article.application-card[data-application-id="{fixture["application_id"]}"]')
    card.wait_for(timeout=30_000)
    card.get_by_role("button", name=f"Open {fixture['title']}").click()
    page.get_by_role("dialog", name=fixture["title"]).wait_for(timeout=30_000)


def exercise_board(page: Page, fixture: dict[str, str], actions: list[dict[str, str]]) -> None:
    click_workspace(page, "Applications", "Application Pipeline")
    app_id = fixture["application_id"]
    title = fixture["title"]
    transition_url = f"/api/applications/{app_id}/transitions"
    card_selector = f'article.application-card[data-application-id="{app_id}"]'
    card = page.locator(card_selector)
    card.wait_for(timeout=30_000)

    # Use the accessible stage selector rather than a synthetic HTML5 drag. Both paths
    # call the same production transition function, but select_option is deterministic
    # in headed Windows Chromium while drag_to may not emit React drop events.
    with page.expect_response(lambda response: transition_url in response.url and response.request.method == "POST") as forward_info:
        card.get_by_label(f"Move {title} to stage").select_option("interviewing")
    assert_success(forward_info.value, "Forward application transition")
    page.get_by_text(f"{title} moved to Interviewing.", exact=True).wait_for(timeout=30_000)
    record_action(actions, "Move application Applied → Interviewing", "passed")

    moved = page.locator(card_selector)
    moved.wait_for(timeout=30_000)
    with page.expect_response(lambda response: transition_url in response.url and response.request.method == "POST") as backward_info:
        moved.get_by_label(f"Move {title} to stage").select_option("applied")
    assert_success(backward_info.value, "Backward application transition")
    page.get_by_text(f"{title} moved to Applied.", exact=True).wait_for(timeout=30_000)
    page.wait_for_load_state("networkidle")
    record_action(actions, "Correct application Interviewing → Applied", "passed")


def exercise_tasks(page: Page, fixture: dict[str, str], actions: list[dict[str, str]]) -> None:
    open_application(page, fixture)
    page.get_by_role("tab", name="Tasks", exact=True).click()
    page.get_by_role("heading", name="Tasks", exact=True).wait_for(timeout=30_000)

    task_title = f"Certification task {time.strftime('%H%M%S')}"
    page.get_by_label("Task title").fill(task_title)
    page.get_by_label("Notes").fill("Initial certification task notes.")
    page.get_by_role("button", name="Add task", exact=True).click()
    page.get_by_text(task_title, exact=True).wait_for(timeout=30_000)
    record_action(actions, "Create application task", "passed")

    item = page.locator("li").filter(has_text=task_title)
    item.get_by_role("button", name="Edit task", exact=True).click()
    corrected = f"{task_title} corrected"
    page.get_by_label("Task title").fill(corrected)
    page.get_by_label("Notes").fill("Corrected certification task notes.")
    page.get_by_role("button", name="Save task changes", exact=True).click()
    page.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    record_action(actions, "Edit application task", "passed")

    corrected_item = page.locator("li").filter(has_text=corrected)
    corrected_item.get_by_role("button", name="Complete", exact=True).click()
    page.get_by_text("Completed", exact=True).wait_for(timeout=30_000)
    record_action(actions, "Complete application task", "passed")


def audit(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    actions: list[dict[str, str]] = []
    workspace_metrics: dict[str, Any] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        fixture = create_fixture(page)
        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)

        for label, heading in [
            ("Capture Jobs", "Capture Jobs"),
            ("Review Inbox", "Review Inbox"),
            ("Applications", "Application Pipeline"),
            ("LinkedIn Profile", "LinkedIn Profile"),
            ("Market Insights", "Market Insights"),
            ("Settings & Data", "Settings & Data"),
        ]:
            click_workspace(page, label, heading)
            workspace_metrics[label] = viewport_metrics(page, label)

        exercise_board(page, fixture, actions)
        exercise_tasks(page, fixture, actions)
        context.close()
        browser.close()

    result = {
        "result": "passed",
        "fixture": fixture,
        "actions": actions,
        "workspace_metrics": workspace_metrics,
    }
    (output_dir / "full-cycle-certification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
