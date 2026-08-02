from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, Response, sync_playwright

API_BASE = "http://127.0.0.1:8000"
APP_URL = "http://127.0.0.1:5173"
VIEWPORT = {"width": 1680, "height": 945}
WORKSPACES = {
    "Capture Jobs": "Capture Jobs",
    "Review Inbox": "Review Inbox",
    "Applications": "Application Pipeline",
    "Market Insights": "Market Insights",
}


def request_json(method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    request = urllib.request.Request(f"{API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            loaded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
    if not isinstance(loaded, dict):
        raise RuntimeError(f"{method} {path} did not return an object")
    return loaded


def seed_application() -> dict[str, str]:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    title = f"Playwright Sidebar Kanban Audit {stamp}"
    intake = request_json(
        "POST",
        "/api/intake/manual",
        {
            "source_url": f"https://example.test/jobs/{stamp}",
            "raw_text": (
                f"{title}\nAudit Systems\nRemote Spain\n"
                "Application support engineer responsible for Windows, Active Directory, "
                "incident management, SQL troubleshooting, APIs, logs, and customer support."
            ),
        },
    )
    posting_id = str(intake.get("posting_id") or "")
    evaluation_id = str(intake.get("evaluation_id") or "")
    if not posting_id or not evaluation_id:
        raise RuntimeError("Manual intake did not return posting_id and evaluation_id")
    request_json(
        "POST",
        f"/api/opportunities/{posting_id}/reviews",
        {"evaluation_id": evaluation_id, "decision": "pursue"},
    )
    application = request_json(
        "POST",
        f"/api/opportunities/{posting_id}/applications",
        {
            "application_url": f"https://example.test/applications/{stamp}",
            "resume_used": "Playwright_Acceptance_CV.pdf",
            "notes": "Disposable Playwright acceptance fixture.",
        },
    )
    application_id = str(application.get("application_id") or "")
    if not application_id:
        raise RuntimeError("Application creation did not return application_id")
    request_json(
        "POST",
        f"/api/applications/{application_id}/transitions",
        {"status": "submitted", "notes": "Seeded in Applied for Playwright acceptance."},
    )
    return {"title": title, "posting_id": posting_id, "application_id": application_id}


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def assert_response_complete(response: Response, action: str) -> None:
    assert_true(response.ok, f"{action} returned HTTP {response.status}: {response.url}")
    completion_error = response.finished()
    assert_true(completion_error is None, f"{action} response did not finish: {completion_error}")


def verify_shell(page: Page, workspace: str) -> dict[str, Any]:
    metrics = page.evaluate(
        """() => {
            const shell = document.querySelector('.workspace-shell');
            const sidebar = document.querySelector('.workspace-sidebar');
            const content = document.querySelector('.workspace-content');
            if (!shell || !sidebar || !content) throw new Error('Workspace shell is incomplete.');
            const shellBox = shell.getBoundingClientRect();
            const sidebarBox = sidebar.getBoundingClientRect();
            const contentBox = content.getBoundingClientRect();
            return {
                viewportWidth: window.innerWidth,
                shell: {left: shellBox.left, right: shellBox.right, width: shellBox.width},
                sidebar: {left: sidebarBox.left, right: sidebarBox.right, width: sidebarBox.width},
                content: {left: contentBox.left, right: contentBox.right, width: contentBox.width},
                documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                sidebarVisible: sidebarBox.width > 0 && sidebarBox.height > 0,
            };
        }"""
    )
    viewport = float(metrics["viewportWidth"])
    assert_true(bool(metrics["sidebarVisible"]), f"Sidebar is not visible in {workspace}")
    assert_true(float(metrics["shell"]["left"]) <= 24, f"Shell starts too far right in {workspace}")
    assert_true(float(metrics["shell"]["right"]) >= viewport - 24, f"Shell is not full width in {workspace}")
    assert_true(float(metrics["sidebar"]["right"]) < float(metrics["content"]["left"]), f"Sidebar overlaps content in {workspace}")
    assert_true(float(metrics["content"]["width"]) >= viewport * 0.65, f"Content is squeezed in {workspace}")
    assert_true(float(metrics["documentOverflow"]) <= 1, f"Document overflow exists in {workspace}")
    return metrics


def open_workspace(page: Page, label: str, heading: str) -> None:
    page.get_by_role("button", name=label, exact=True).click()
    page.get_by_role("heading", name=heading, exact=True).wait_for(timeout=30_000)


def audit(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture = seed_application()
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []
    workspace_metrics: dict[str, Any] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("requestfailed", lambda request: failed_requests.append(f"{request.method} {request.url}: {request.failure}"))

        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)
        page.get_by_role("button", name="Capture Jobs", exact=True).wait_for()

        for label, heading in WORKSPACES.items():
            open_workspace(page, label, heading)
            workspace_metrics[label] = verify_shell(page, label)
            page.screenshot(path=output_dir / f"workspace-{label.lower().replace(' ', '-')}.png", full_page=True)

        open_workspace(page, "Applications", "Application Pipeline")
        board_metrics = page.locator(".application-board").evaluate(
            """board => ({
                overflowX: getComputedStyle(board).overflowX,
                documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            })"""
        )
        assert_true(board_metrics["overflowX"] in {"auto", "scroll"}, "Board does not own horizontal scrolling")
        assert_true(int(board_metrics["documentOverflow"]) <= 1, "Board causes document-level overflow")

        title = fixture["title"]
        app_id = fixture["application_id"]
        transition_url = f"/api/applications/{app_id}/transitions"
        card_selector = f'article.application-card[data-application-id="{app_id}"]'
        card = page.locator(card_selector)
        card.wait_for(timeout=30_000)
        assert_true(page.locator(card_selector).count() == 1, "Application is not rendered exactly once")

        with page.expect_response(lambda response: transition_url in response.url and response.request.method == "POST") as forward_info:
            card.drag_to(page.locator("section.application-lane-interviewing"))
        assert_response_complete(forward_info.value, "Forward application transition")
        page.get_by_text(f"{title} moved to Interviewing.", exact=True).wait_for(timeout=30_000)

        moved = page.locator(card_selector)
        with page.expect_response(lambda response: transition_url in response.url and response.request.method == "POST") as backward_info:
            moved.get_by_label(f"Move {title} to stage").select_option("applied")
        assert_response_complete(backward_info.value, "Backward application transition")
        page.get_by_text(f"{title} moved to Applied.", exact=True).wait_for(timeout=30_000)
        page.wait_for_load_state("networkidle")

        page.reload(wait_until="networkidle")
        open_workspace(page, "Applications", "Application Pipeline")
        persisted = page.locator("section.application-lane-applied article.application-card").filter(has_text=title)
        persisted.wait_for(timeout=30_000)
        assert_true(page.locator(card_selector).count() == 1, "Corrected card duplicated after reload")
        persisted.get_by_role("button", name=f"Open {title}").click()
        page.get_by_role("dialog", name=title).wait_for()
        page.get_by_role("tab", name="Timeline", exact=True).click()
        page.get_by_text("submitted → recruiter screen", exact=True).wait_for(timeout=30_000)
        page.get_by_text("recruiter screen → submitted", exact=True).wait_for(timeout=30_000)
        page.screenshot(path=output_dir / "timeline-audited-forward-and-backward.png", full_page=True)
        browser.close()

    summary = {
        "fixture": fixture,
        "viewport": VIEWPORT,
        "workspace_metrics": workspace_metrics,
        "board_metrics": board_metrics,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "failed_requests": failed_requests,
    }
    (output_dir / "audit-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
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
