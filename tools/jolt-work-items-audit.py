from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import Page, Response, sync_playwright

APP_URL = "http://127.0.0.1:5173"
VIEWPORT = {"width": 1680, "height": 945}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def snapshot(page: Page, output_dir: Path, name: str, summary: dict[str, object]) -> None:
    path = output_dir / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    screenshots = summary.setdefault("screenshots", [])
    assert isinstance(screenshots, list)
    screenshots.append(path.name)


def horizontal_overflow(page: Page) -> int:
    return int(page.evaluate("Math.max(0, document.documentElement.scrollWidth - window.innerWidth)"))


def local_datetime_value(value: datetime) -> str:
    return value.astimezone().strftime("%Y-%m-%dT%H:%M")


def main() -> int:
    output_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, object] = {
        "started_at": now_iso(),
        "app_url": APP_URL,
        "viewport": VIEWPORT,
        "console": [],
        "page_errors": [],
        "failed_requests": [],
        "responses": [],
        "screenshots": [],
        "observations": {},
        "ux_checks": {},
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT)
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()

        page.on(
            "console",
            lambda message: summary["console"].append(
                {"type": message.type, "text": message.text, "timestamp": now_iso()}
            ),
        )
        page.on(
            "pageerror",
            lambda error: summary["page_errors"].append(
                {"message": str(error), "timestamp": now_iso()}
            ),
        )
        page.on(
            "requestfailed",
            lambda request: summary["failed_requests"].append(
                {
                    "method": request.method,
                    "url": request.url,
                    "failure": request.failure,
                    "timestamp": now_iso(),
                }
            ),
        )

        def record_response(response: Response) -> None:
            if response.url.startswith("http://127.0.0.1:8000"):
                summary["responses"].append(
                    {
                        "status": response.status,
                        "method": response.request.method,
                        "url": response.url,
                    }
                )

        page.on("response", record_response)
        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)
        page.get_by_role("button", name="Applications").click()
        page.locator("#application-dashboard-heading").wait_for(state="visible", timeout=30_000)

        managed_card = page.locator(
            ".application-lane-applied .application-card-open, "
            ".application-lane-interviewing .application-card-open, "
            ".application-lane-offer .application-card-open, "
            ".application-lane-closed .application-card-open"
        ).first
        if managed_card.count() == 0:
            raise RuntimeError("No persisted application is available for the work-items audit.")

        managed_card.click()
        workspace = page.get_by_role("dialog")
        workspace.wait_for(state="visible", timeout=30_000)
        observations = summary["observations"]
        ux_checks = summary["ux_checks"]
        assert isinstance(observations, dict)
        assert isinstance(ux_checks, dict)

        observations["workspace_title"] = page.locator("#application-detail-title").inner_text()
        observations["workspace_tabs"] = workspace.get_by_role("tab").all_inner_texts()
        ux_checks["workspace_horizontal_overflow_px"] = horizontal_overflow(page)

        task_title = f"Playwright audit task {datetime.now().strftime('%Y%m%d-%H%M%S')}"
        tasks_tab = workspace.get_by_role("tab", name="Tasks")
        tasks_tab.click()
        page.locator("#application-tasks-heading").wait_for(state="visible", timeout=30_000)
        snapshot(page, output_dir, "01-tasks-empty-or-existing", summary)

        workspace.get_by_label("Task title").fill(task_title)
        workspace.get_by_label("Due date and time").fill(
            local_datetime_value(datetime.now(timezone.utc) + timedelta(days=1))
        )
        workspace.get_by_label("Notes").fill("Created by the supervised Playwright acceptance audit.")
        workspace.get_by_role("button", name="Add task").click()
        workspace.get_by_text(task_title, exact=True).wait_for(state="visible", timeout=30_000)
        snapshot(page, output_dir, "02-task-created", summary)

        task_item = workspace.locator(".work-item-list li", has_text=task_title)
        task_item.get_by_role("button", name="Complete").click()
        task_item.get_by_role("button", name="Reopen").wait_for(state="visible", timeout=30_000)
        snapshot(page, output_dir, "03-task-completed", summary)
        task_item.get_by_role("button", name="Reopen").click()
        task_item.get_by_role("button", name="Complete").wait_for(state="visible", timeout=30_000)
        snapshot(page, output_dir, "04-task-reopened", summary)

        interviews_tab = workspace.get_by_role("tab", name="Interviews")
        interviews_tab.click()
        page.locator("#application-interviews-heading").wait_for(state="visible", timeout=30_000)
        snapshot(page, output_dir, "05-interviews-empty-or-existing", summary)

        scheduled_at = datetime.now(timezone.utc) + timedelta(days=2)
        workspace.get_by_label("Interview type").select_option("technical_interview")
        workspace.get_by_label("Date and time").fill(local_datetime_value(scheduled_at))
        workspace.get_by_label("Timezone").fill("Europe/Madrid")
        workspace.get_by_label("Format or location").fill("Teams — supervised audit")
        workspace.get_by_label("Participants").fill("Audit interviewer")
        workspace.get_by_label("Preparation notes").fill(
            "Verify application Tasks, Interviews, and Timeline integration."
        )
        workspace.get_by_role("button", name="Schedule interview").click()
        interview_item = workspace.locator(".interview-list li", has_text="technical interview").last
        interview_item.wait_for(state="visible", timeout=30_000)
        snapshot(page, output_dir, "06-interview-scheduled", summary)
        interview_item.get_by_role("button", name="Cancel").click()
        interview_item.get_by_text("cancelled", exact=True).wait_for(state="visible", timeout=30_000)
        snapshot(page, output_dir, "07-interview-cancelled", summary)

        timeline_tab = workspace.get_by_role("tab", name="Timeline")
        timeline_tab.click()
        page.locator("#application-timeline-heading").wait_for(state="visible", timeout=30_000)
        page.wait_for_timeout(500)
        timeline_text = workspace.locator(".application-timeline").inner_text()
        expected_events = [
            "task created",
            "task completed",
            "task reopened",
            "interview created",
            "interview cancelled",
        ]
        observations["timeline_event_count"] = workspace.locator(".application-timeline li").count()
        observations["expected_timeline_events"] = {
            event: event in timeline_text.lower() for event in expected_events
        }
        snapshot(page, output_dir, "08-timeline-after-work-items", summary)

        ux_checks["final_horizontal_overflow_px"] = horizontal_overflow(page)
        ux_checks["workspace_scroll_height"] = workspace.evaluate("element => element.scrollHeight")
        ux_checks["workspace_client_height"] = workspace.evaluate("element => element.clientHeight")
        ux_checks["all_expected_events_visible"] = all(
            observations["expected_timeline_events"].values()
        )

        context.tracing.stop(path=str(output_dir / "playwright-trace.zip"))
        browser.close()

    responses = summary["responses"]
    assert isinstance(responses, list)
    summary["http_errors"] = [response for response in responses if int(response["status"]) >= 400]
    summary["finished_at"] = now_iso()
    (output_dir / "audit-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
