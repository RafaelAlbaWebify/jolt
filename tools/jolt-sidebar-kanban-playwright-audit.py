from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

API_BASE = "http://127.0.0.1:8000"
APP_URL = "http://127.0.0.1:5173"
VIEWPORT = {"width": 1680, "height": 945}
WORKSPACES = {
    "Review Inbox": "Review Inbox",
    "Application Pipeline": "Application Pipeline",
    "Market Insights": "Market Insights",
    "Capture & Evidence": "Capture & Evidence",
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


def shell_metrics(page: Page) -> dict[str, Any]:
    return page.evaluate(
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
                sidebarVisible: sidebarBox.width > 0 && sidebarBox.height > 0 && sidebarBox.right > 0 && sidebarBox.left < window.innerWidth,
            };
        }"""
    )


def verify_shell(page: Page, workspace: str) -> dict[str, Any]:
    metrics = shell_metrics(page)
    viewport = float(metrics["viewportWidth"])
    shell = metrics["shell"]
    sidebar = metrics["sidebar"]
    content = metrics["content"]
    assert_true(bool(metrics["sidebarVisible"]), f"Sidebar is not visible in {workspace}")
    assert_true(float(shell["left"]) <= 24, f"Shell does not start near the left edge in {workspace}")
    assert_true(float(shell["right"]) >= viewport - 24, f"Shell does not use the full viewport width in {workspace}")
    assert_true(float(sidebar["right"]) < float(content["left"]), f"Sidebar and content overlap in {workspace}")
    assert_true(float(content["width"]) >= viewport * 0.65, f"Main content is squeezed in {workspace}")
    assert_true(float(metrics["documentOverflow"]) <= 1, f"Document overflow exists in {workspace}")
    return metrics


def audit(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture = seed_application()
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []
    workspace_metrics: dict[str, Any] = {}
    heading_matches: dict[str, bool] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "requestfailed",
            lambda request: failed_requests.append(
                f"{request.method} {request.url}: {request.failure}"
            ),
        )

        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)
        page.get_by_role("button", name="Capture & Evidence", exact=True).wait_for()

        for label, current_heading in WORKSPACES.items():
            page.get_by_role("button", name=label, exact=True).click()
            page.get_by_role("heading", name=current_heading, exact=True).wait_for(
                timeout=30_000
            )
            workspace_metrics[label] = verify_shell(page, label)
            heading_matches[label] = (
                page.get_by_role("heading", name=current_heading, exact=True).count() > 0
            )
            safe_label = label.lower().replace(" ", "-").replace("&", "and")
            page.screenshot(
                path=output_dir / f"workspace-{safe_label}.png", full_page=True
            )

        page.get_by_role("button", name="Application Pipeline", exact=True).click()
        page.get_by_role("heading", name="Application Pipeline", exact=True).wait_for()
        board_metrics = page.locator(".application-board").evaluate(
            """board => ({
                clientWidth: board.clientWidth,
                scrollWidth: board.scrollWidth,
                overflowX: getComputedStyle(board).overflowX,
                documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            })"""
        )
        assert_true(
            board_metrics["overflowX"] in {"auto", "scroll"},
            "Board does not own horizontal scrolling",
        )
        assert_true(
            int(board_metrics["documentOverflow"]) <= 1,
            "Board causes document-level overflow",
        )

        title = fixture["title"]
        card_selector = (
            f'article.application-card[data-application-id="{fixture["application_id"]}"]'
        )
        card = page.locator(card_selector)
        assert_true(
            card.count() == 1,
            "Audit application is not rendered exactly once before the move",
        )
        card.wait_for(timeout=30_000)
        assert_true(card.get_attribute("draggable") == "true", "Prepared audit card is not draggable")
        applied_lane = page.locator("section.application-lane-applied")
        interviewing_lane = page.locator("section.application-lane-interviewing")
        assert_true(
            applied_lane.locator(
                f'article[data-application-id="{fixture["application_id"]}"]'
            ).count()
            == 1,
            "Audit card is not in Applied before the move",
        )
        card.drag_to(interviewing_lane)
        page.get_by_text(f"{title} moved to Interviewing.", exact=True).wait_for(
            timeout=30_000
        )
        moved_card = page.locator(card_selector)
        moved_card.wait_for(timeout=30_000)
        assert_true(
            applied_lane.locator(
                f'article[data-application-id="{fixture["application_id"]}"]'
            ).count()
            == 0,
            "Moved card remains in the source lane",
        )
        assert_true(
            page.locator(card_selector).count() == 1,
            "Moved card is duplicated after the transition",
        )
        page.screenshot(
            path=output_dir / "applications-after-forward-drag.png", full_page=True
        )

        backward_control = moved_card.get_by_label(f"Move {title} to lane")
        backward_control.select_option("applied")
        page.get_by_text(f"{title} moved to Applied.", exact=True).wait_for(timeout=30_000)
        corrected_card = applied_lane.locator(
            f'article[data-application-id="{fixture["application_id"]}"]'
        )
        corrected_card.wait_for(timeout=30_000)
        assert_true(
            interviewing_lane.locator(
                f'article[data-application-id="{fixture["application_id"]}"]'
            ).count()
            == 0,
            "Corrected card remains in Interviewing",
        )
        assert_true(
            page.locator(card_selector).count() == 1,
            "Corrected card is duplicated after the backward move",
        )
        page.screenshot(
            path=output_dir / "applications-after-backward-correction.png",
            full_page=True,
        )

        page.reload(wait_until="networkidle")
        page.get_by_role("button", name="Application Pipeline", exact=True).click()
        page.get_by_role("heading", name="Application Pipeline", exact=True).wait_for()
        persisted_card = page.locator(
            "section.application-lane-applied article.application-card"
        ).filter(has_text=title)
        persisted_card.wait_for(timeout=30_000)
        assert_true(
            page.locator(card_selector).count() == 1,
            "Corrected card is duplicated after reload",
        )
        persisted_card.get_by_role("button", name=f"Open {title}").click()
        page.get_by_role("dialog", name=title).wait_for()
        page.get_by_role("tab", name="Timeline", exact=True).click()
        page.get_by_text("submitted → recruiter screen", exact=True).wait_for(
            timeout=30_000
        )
        page.get_by_text("recruiter screen → submitted", exact=True).wait_for(
            timeout=30_000
        )
        forward_notes = page.get_by_text(
            "Moved on application board from applied to interviewing.", exact=True
        )
        backward_notes = page.get_by_text(
            "Moved on application board from interviewing to applied.", exact=True
        )
        forward_notes.wait_for(timeout=30_000)
        backward_notes.wait_for(timeout=30_000)
        assert_true(
            forward_notes.count() == 1,
            "The forward board move produced duplicate timeline events",
        )
        assert_true(
            backward_notes.count() == 1,
            "The backward board correction produced duplicate timeline events",
        )
        page.screenshot(
            path=output_dir / "timeline-audited-forward-and-backward.png",
            full_page=True,
        )
        browser.close()

    summary = {
        "fixture": fixture,
        "viewport": VIEWPORT,
        "workspace_metrics": workspace_metrics,
        "workspace_heading_matches_navigation": heading_matches,
        "board_metrics": board_metrics,
        "sidebar_visible_all_workspaces": all(
            bool(item["sidebarVisible"]) for item in workspace_metrics.values()
        ),
        "full_width_all_workspaces": all(
            float(item["shell"]["left"]) <= 24
            and float(item["shell"]["right"]) >= VIEWPORT["width"] - 24
            for item in workspace_metrics.values()
        ),
        "document_overflow_all_workspaces": all(
            float(item["documentOverflow"]) <= 1
            for item in workspace_metrics.values()
        ),
        "forward_and_backward_moves_persisted_after_reload": True,
        "timeline_contains_audited_forward_and_backward_moves": True,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "failed_requests": failed_requests,
    }
    (output_dir / "audit-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    assert_true(not console_errors, f"Browser console errors: {console_errors}")
    assert_true(not page_errors, f"Page errors: {page_errors}")
    assert_true(not failed_requests, f"Failed browser requests: {failed_requests}")
    assert_true(
        all(heading_matches.values()),
        f"Workspace headings do not match navigation: {heading_matches}",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
