from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Page, Response, sync_playwright

APP_URL = "http://127.0.0.1:5173"
API_URL = "http://127.0.0.1:8000"
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
            if response.url.startswith(API_URL):
                summary["responses"].append(
                    {
                        "status": response.status,
                        "method": response.request.method,
                        "url": response.url,
                    }
                )

        page.on("response", record_response)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        title = f"JOLT Stage Reversal Audit {stamp}"
        intake = page.request.post(
            f"{API_URL}/api/intake/manual",
            data={
                "source_url": f"https://example.test/jolt-stage-audit/{stamp}",
                "raw_text": (
                    f"{title}\nAudit Systems\nLocation: Remote Spain\n"
                    "Application support, SQL troubleshooting, APIs, logs, and incident ownership."
                ),
            },
        )
        if not intake.ok:
            raise RuntimeError(f"Audit fixture intake failed: {intake.status}")
        intake_data = intake.json()

        review = page.request.post(
            f"{API_URL}/api/opportunities/{intake_data['posting_id']}/reviews",
            data={
                "evaluation_id": intake_data["evaluation_id"],
                "decision": "pursue",
                "reason_code": "playwright_audit",
                "notes": "Supervised stage-reversal acceptance fixture.",
            },
        )
        if not review.ok:
            raise RuntimeError(f"Audit fixture review failed: {review.status}")

        application = page.request.post(
            f"{API_URL}/api/opportunities/{intake_data['posting_id']}/applications",
            data={
                "resume_used": "JOLT_STAGE_AUDIT_RESUME.pdf",
                "notes": "Created by the supervised stage-reversal acceptance audit.",
            },
        )
        if not application.ok:
            raise RuntimeError(f"Audit fixture application failed: {application.status}")
        application_data = application.json()

        observations = summary["observations"]
        ux_checks = summary["ux_checks"]
        assert isinstance(observations, dict)
        assert isinstance(ux_checks, dict)
        observations["fixture_title"] = title
        observations["application_id"] = application_data["application_id"]

        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)
        page.get_by_role("button", name="Applications").click()
        page.locator("#application-dashboard-heading").wait_for(state="visible", timeout=30_000)
        audit_card = page.locator(".application-card", has_text=title)
        audit_card.wait_for(state="visible", timeout=30_000)
        snapshot(page, output_dir, "01-board-preparing", summary)

        audit_card.locator(".application-card-open").click()
        workspace = page.get_by_role("dialog")
        workspace.wait_for(state="visible", timeout=30_000)
        workspace.locator(".application-workflow > summary").click()
        current_stage = workspace.locator(".workflow-current-stage h4")
        current_stage.wait_for(state="visible", timeout=30_000)
        observations["initial_stage"] = current_stage.inner_text()
        snapshot(page, output_dir, "02-workspace-preparing", summary)

        stage_select = workspace.get_by_label("Stage")
        notes = workspace.get_by_label("Activity or correction notes")

        notes.fill("Advance the audit fixture to a late interview stage.")
        stage_select.select_option("technical_interview")
        workspace.get_by_role("button", name="Save stage").click()
        current_stage.get_by_text("technical interview", exact=True).wait_for(
            state="visible", timeout=30_000
        )
        snapshot(page, output_dir, "03-forward-technical-interview", summary)

        notes.fill("Correct the recorded stage backward to submitted.")
        stage_select.select_option("submitted")
        workspace.get_by_role("button", name="Save stage").click()
        current_stage.get_by_text("submitted", exact=True).wait_for(state="visible", timeout=30_000)
        observations["backward_stage"] = current_stage.inner_text()
        snapshot(page, output_dir, "04-backward-submitted", summary)

        notes.fill("Close the audit fixture to verify reopening.")
        workspace.get_by_label("Outcome").select_option("rejected_by_employer")
        workspace.get_by_role("button", name="Record final outcome").click()
        workspace.get_by_text("Final outcome: rejected by employer", exact=True).wait_for(
            state="visible", timeout=30_000
        )
        snapshot(page, output_dir, "05-closed-outcome", summary)

        notes.fill("Reopen the closed audit fixture at recruiter screen.")
        stage_select.select_option("recruiter_screen")
        workspace.get_by_role("button", name="Save stage").click()
        current_stage.get_by_text("recruiter screen", exact=True).wait_for(
            state="visible", timeout=30_000
        )
        observations["reopened_stage"] = current_stage.inner_text()
        snapshot(page, output_dir, "06-reopened-recruiter-screen", summary)

        workspace.get_by_role("button", name="Close").click()
        workspace.wait_for(state="hidden", timeout=30_000)
        interviewing_card = page.locator(
            ".application-lane-interviewing .application-card", has_text=title
        )
        interviewing_card.wait_for(state="visible", timeout=30_000)
        observations["board_lane_after_reopen"] = "interviewing"
        snapshot(page, output_dir, "07-board-after-reopen", summary)

        interviewing_card.locator(".application-card-open").click()
        workspace = page.get_by_role("dialog")
        workspace.wait_for(state="visible", timeout=30_000)
        workspace.locator(".application-workflow > summary").click()
        persisted_stage = workspace.locator(".workflow-current-stage h4")
        persisted_stage.get_by_text("recruiter screen", exact=True).wait_for(
            state="visible", timeout=30_000
        )
        observations["persisted_stage_after_reopen"] = persisted_stage.inner_text()

        workspace.get_by_role("tab", name="Timeline").click()
        page.locator("#application-timeline-heading").wait_for(state="visible", timeout=30_000)
        timeline_text = workspace.locator(".application-timeline").inner_text().lower()
        expected_fragments = [
            "technical interview",
            "submitted",
            "rejected by employer",
            "recruiter screen",
        ]
        observations["expected_timeline_fragments"] = {
            fragment: fragment in timeline_text for fragment in expected_fragments
        }
        snapshot(page, output_dir, "08-timeline-stage-reversal", summary)

        ux_checks["horizontal_overflow_px"] = horizontal_overflow(page)
        ux_checks["workspace_horizontal_overflow_px"] = int(
            workspace.evaluate("element => Math.max(0, element.scrollWidth - element.clientWidth)")
        )
        ux_checks["all_expected_timeline_fragments"] = all(
            observations["expected_timeline_fragments"].values()
        )
        ux_checks["reopened_card_in_interviewing_lane"] = interviewing_card.count() == 1

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
