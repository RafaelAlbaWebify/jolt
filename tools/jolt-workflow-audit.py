from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Locator, Page, Response, sync_playwright

APP_URL = "http://127.0.0.1:5173"
VIEWPORT = {"width": 1680, "height": 945}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_text(page: Page, selector: str) -> str:
    locator = page.locator(selector)
    if locator.count() == 0:
        return ""
    return locator.first.inner_text().strip()


def snapshot(page: Page, output_dir: Path, name: str, summary: dict[str, object]) -> None:
    path = output_dir / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    summary.setdefault("screenshots", []).append(path.name)


def box(locator: Locator) -> dict[str, float] | None:
    value = locator.bounding_box()
    if value is None:
        return None
    return {key: round(float(value[key]), 1) for key in ("x", "y", "width", "height")}


def horizontal_overflow(page: Page) -> int:
    return page.evaluate("Math.max(0, document.documentElement.scrollWidth - window.innerWidth)")


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
        "timings_ms": {},
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

        started = time.perf_counter()
        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)
        summary["timings_ms"]["initial_load"] = round((time.perf_counter() - started) * 1000)
        snapshot(page, output_dir, "01-opportunities", summary)

        observations = summary["observations"]
        ux_checks = summary["ux_checks"]
        observations["opportunities_heading"] = safe_text(page, "#queue-heading")
        observations["opportunity_rows"] = page.locator(".opportunity-row").count()
        observations["visible_error"] = safe_text(page, "[role='alert']")
        ux_checks["opportunities_horizontal_overflow_px"] = horizontal_overflow(page)

        active_filter = page.get_by_role("button", name=lambda name: name.startswith("active (")).first
        if active_filter.count() > 0 and "active (0)" not in active_filter.inner_text():
            active_filter.click()
            page.wait_for_timeout(250)

        inspect = page.get_by_role("button", name="Inspect").first
        if inspect.count() > 0:
            started = time.perf_counter()
            inspect.click()
            inspector = page.get_by_role("dialog")
            inspector.wait_for(state="visible", timeout=30_000)
            page.locator(".inspector-loading").wait_for(state="hidden", timeout=60_000)
            summary["timings_ms"]["inspector_open"] = round((time.perf_counter() - started) * 1000)
            observations["inspector_title"] = safe_text(page, "#opportunity-inspector-title")
            observations["inspector_buttons"] = inspector.get_by_role("button").all_inner_texts()
            observations["inspector_links"] = inspector.get_by_role("link").all_inner_texts()
            observations["inspector_application_workflows"] = inspector.locator(".application-workflow").count()
            observations["inspector_application_handoffs"] = inspector.locator(".opportunity-application-handoff").count()
            observations["inspector_stage_controls"] = inspector.get_by_label("Stage").count()
            ux_checks["inspector_box"] = box(inspector)
            ux_checks["inspector_horizontal_overflow_px"] = horizontal_overflow(page)
            snapshot(page, output_dir, "02-inspector", summary)
            inspector.get_by_role("button", name="Close").click()

        page.get_by_role("button", name="Applications").click()
        page.locator("#application-dashboard-heading").wait_for(state="visible", timeout=30_000)
        page.wait_for_timeout(1_000)
        observations["applications_error"] = safe_text(page, "[role='alert']")
        observations["application_lanes"] = page.locator(".application-lane").count()
        observations["application_lane_titles"] = page.locator(".application-lane-header h3").all_inner_texts()
        observations["application_cards"] = page.locator(".application-card").count()
        observations["application_lane_counts"] = page.locator(".application-lane-header > strong").all_inner_texts()
        ux_checks["application_board_box"] = box(page.locator(".application-board"))
        ux_checks["application_board_horizontal_overflow_px"] = horizontal_overflow(page)
        ux_checks["all_five_lanes_visible"] = observations["application_lanes"] == 5
        snapshot(page, output_dir, "03-applications-board", summary)

        managed_card = page.locator(
            ".application-lane-applied .application-card-open, "
            ".application-lane-interviewing .application-card-open, "
            ".application-lane-offer .application-card-open, "
            ".application-lane-closed .application-card-open"
        ).first
        candidate_card = managed_card if managed_card.count() > 0 else page.locator(".application-card-open").first
        if candidate_card.count() > 0:
            started = time.perf_counter()
            candidate_card.click()
            workspace = page.get_by_role("dialog")
            workspace.wait_for(state="visible", timeout=30_000)
            summary["timings_ms"]["application_workspace_open"] = round((time.perf_counter() - started) * 1000)
            observations["workspace_title"] = safe_text(page, "#application-detail-title")
            observations["workspace_tabs"] = page.get_by_role("tab").all_inner_texts()
            observations["workspace_selected_tab"] = page.get_by_role("tab", selected=True).inner_text()
            observations["workspace_workflow_count"] = workspace.locator(".application-workflow").count()
            ux_checks["workspace_box"] = box(workspace)
            ux_checks["workspace_horizontal_overflow_px"] = horizontal_overflow(page)
            ux_checks["workspace_fits_viewport"] = bool(
                (workspace_box := workspace.bounding_box())
                and workspace_box["width"] <= VIEWPORT["width"]
                and workspace_box["height"] <= VIEWPORT["height"]
            )
            snapshot(page, output_dir, "04-application-overview", summary)

            timeline_tab = workspace.get_by_role("tab", name="Timeline")
            if timeline_tab.count() > 0:
                timeline_tab.click()
                page.wait_for_timeout(400)
                observations["timeline_heading"] = safe_text(page, "#application-timeline-heading")
                observations["timeline_events"] = workspace.locator(".application-timeline li").count()
                observations["timeline_loading"] = workspace.get_by_text("Loading application timeline…").count()
                snapshot(page, output_dir, "05-application-timeline", summary)
            workspace.get_by_role("button", name="Close").click()

        page.get_by_role("button", name="Market").click()
        page.get_by_role("heading", name="Market intelligence").wait_for(state="visible", timeout=30_000)
        page.wait_for_timeout(750)
        observations["market_cards"] = page.locator(".market-summary-card").count()
        observations["market_error"] = safe_text(page, "[role='alert']")
        ux_checks["market_horizontal_overflow_px"] = horizontal_overflow(page)
        snapshot(page, output_dir, "06-market", summary)

        page.get_by_role("button", name="Opportunities").click()
        page.wait_for_timeout(400)
        observations["opportunities_after_roundtrip"] = page.locator(".opportunity-row").count()
        snapshot(page, output_dir, "07-opportunities-return", summary)

        context.tracing.stop(path=str(output_dir / "playwright-trace.zip"))
        browser.close()

    summary["http_errors"] = [
        response for response in summary["responses"] if int(response["status"]) >= 400
    ]
    summary["finished_at"] = now_iso()
    (output_dir / "audit-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
