from __future__ import annotations

import argparse
import html
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page, sync_playwright

API_BASE = "http://127.0.0.1:8000"
APP_URL = "http://127.0.0.1:5173"
VIEWPORT = {"width": 1680, "height": 945}
WORKSPACES = {
    "Capture Jobs": "Capture Jobs",
    "Review Inbox": "Review Inbox",
    "Applications": "Application Pipeline",
    "LinkedIn Profile": "LinkedIn Profile",
    "Market Insights": "Market Insights",
}


def request_json(method: str, path: str, payload: dict[str, object] | None = None) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    request = urllib.request.Request(f"{API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc


def seed_application() -> dict[str, str]:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    title = f"Full Cycle Certification {stamp}"
    source_url = f"https://example.test/jobs/full-cycle-{stamp}"
    payload = {
        "source_url": source_url,
        "raw_text": (
            f"{title}\nCertification Systems\nRemote Spain\n"
            "Application support engineer responsible for Windows, Active Directory, SQL, APIs, "
            "incident management, logs, customer support, runbooks, and production troubleshooting."
        ),
    }
    intake = request_json("POST", "/api/intake/manual", payload)
    duplicate = request_json("POST", "/api/intake/manual", payload)
    if duplicate.get("identity_status") != "confirmed_duplicate":
        raise AssertionError("Repeated manual intake was not classified as a confirmed duplicate.")

    posting_id = str(intake["posting_id"])
    evaluation_id = str(intake["evaluation_id"])
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
            "resume_used": "Full_Cycle_Certification_CV.pdf",
            "notes": "Disposable full-cycle Playwright certification fixture.",
        },
    )
    application_id = str(application["application_id"])
    request_json(
        "POST",
        f"/api/applications/{application_id}/transitions",
        {"status": "submitted", "notes": "Prepared for full-cycle certification."},
    )
    return {
        "title": title,
        "source_url": source_url,
        "posting_id": posting_id,
        "evaluation_id": evaluation_id,
        "application_id": application_id,
        "duplicate_source_document_id": str(duplicate["source_document_id"]),
    }


def record_action(actions: list[dict[str, str]], name: str, status: str, detail: str = "") -> None:
    actions.append({"name": name, "status": status, "detail": detail})


def screenshot(page: Page, output_dir: Path, sequence: int, name: str) -> int:
    safe_name = "".join(character if character.isalnum() or character in "-_" else "-" for character in name)
    page.screenshot(path=output_dir / "screenshots" / f"{sequence:03d}-{safe_name}.png", full_page=True)
    return sequence + 1


def inventory_controls(page: Page, workspace: str) -> list[dict[str, str]]:
    return page.locator("button, a, select, input, textarea, summary").evaluate_all(
        """(nodes, workspace) => nodes.map((node) => ({
            workspace,
            tag: node.tagName.toLowerCase(),
            role: node.getAttribute('role') || '',
            type: node.getAttribute('type') || '',
            name: node.getAttribute('aria-label') || node.getAttribute('name') || '',
            text: (node.innerText || node.getAttribute('value') || node.getAttribute('placeholder') || '').trim().replace(/\\s+/g, ' ').slice(0, 240),
            disabled: node.matches(':disabled') ? 'true' : 'false',
            href: node.getAttribute('href') || '',
        }))""",
        workspace,
    )


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
    card_selector = f'article.application-card[data-application-id="{app_id}"]'
    card = page.locator(card_selector)
    card.wait_for(timeout=30_000)
    card.drag_to(page.locator("section.application-lane-interviewing"))
    page.get_by_text(f"{title} moved to Interviewing.", exact=True).wait_for(timeout=30_000)
    record_action(actions, "Move application Applied → Interviewing", "passed")

    moved = page.locator(card_selector)
    moved.wait_for(timeout=30_000)
    moved.get_by_label(f"Move {title} to stage").select_option("applied")
    page.get_by_text(f"{title} moved to Applied.", exact=True).wait_for(timeout=30_000)
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
    corrected_item.get_by_role("button", name="Reopen", exact=True).wait_for(timeout=30_000)
    record_action(actions, "Complete application task", "passed")
    corrected_item.get_by_role("button", name="Reopen", exact=True).click()
    corrected_item.get_by_role("button", name="Complete", exact=True).wait_for(timeout=30_000)
    record_action(actions, "Reopen application task", "passed")

    page.reload(wait_until="networkidle")
    open_application(page, fixture)
    page.get_by_role("tab", name="Tasks", exact=True).click()
    page.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    record_action(actions, "Task persists after reload", "passed")

    page.get_by_role("tab", name="Timeline", exact=True).click()
    page.get_by_text("task_updated", exact=False).first.wait_for(timeout=30_000)
    page.get_by_text(corrected, exact=False).first.wait_for(timeout=30_000)
    record_action(actions, "Task correction visible in timeline", "passed")


def write_report(output_dir: Path, summary: dict[str, Any]) -> None:
    rows = "".join(
        f"<tr><td>{html.escape(action['name'])}</td><td>{html.escape(action['status'])}</td>"
        f"<td>{html.escape(action['detail'])}</td></tr>"
        for action in summary["actions"]
    )
    report = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>JOLT full-cycle certification</title>
<style>body{{font-family:system-ui;margin:2rem;max-width:1200px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:.5rem;text-align:left}}code,pre{{background:#f4f4f4;padding:.2rem .4rem}}.passed{{color:#176b2c}}</style></head>
<body><h1>JOLT full-cycle Playwright certification</h1>
<p>Result: <strong class="passed">{html.escape(summary['result'])}</strong></p>
<p>Fixture application: <code>{html.escape(summary['fixture']['application_id'])}</code></p>
<h2>Actions</h2><table><thead><tr><th>Action</th><th>Status</th><th>Detail</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Browser diagnostics</h2><pre>{html.escape(json.dumps(summary['browser_diagnostics'], indent=2))}</pre>
<h2>Control inventory</h2><p>{sum(len(value) for value in summary['control_inventory'].values())} controls observed across all workspaces.</p>
</body></html>"""
    (output_dir / "certification-report.html").write_text(report, encoding="utf-8")


def audit(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "screenshots").mkdir(exist_ok=True)
    (output_dir / "video").mkdir(exist_ok=True)
    fixture = seed_application()
    actions: list[dict[str, str]] = []
    console_errors: list[str] = []
    console_warnings: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []
    unexpected_responses: list[str] = []
    inventory: dict[str, list[dict[str, str]]] = {}
    shell_metrics: dict[str, dict[str, Any]] = {}
    sequence = 1

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context: BrowserContext = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=output_dir / "video",
            record_video_size=VIEWPORT,
        )
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else console_warnings.append(message.text) if message.type == "warning" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("requestfailed", lambda request: failed_requests.append(f"{request.method} {request.url}: {request.failure}"))
        page.on(
            "response",
            lambda response: unexpected_responses.append(f"{response.status} {response.request.method} {response.url}")
            if response.status >= 500
            else None,
        )
        try:
            page.goto(APP_URL, wait_until="networkidle", timeout=60_000)
            page.get_by_role("button", name="Capture Jobs", exact=True).wait_for()
            for label, heading in WORKSPACES.items():
                click_workspace(page, label, heading)
                shell_metrics[label] = verify_shell(page, label)
                inventory[label] = inventory_controls(page, label)
                sequence = screenshot(page, output_dir, sequence, f"workspace-{label.lower()}")
                record_action(actions, f"Open and inspect {label} workspace", "passed")

            exercise_board(page, fixture, actions)
            sequence = screenshot(page, output_dir, sequence, "applications-after-board-correction")
            exercise_tasks(page, fixture, actions)
            sequence = screenshot(page, output_dir, sequence, "task-correction-timeline")

            if console_errors:
                raise AssertionError(f"Browser console errors: {console_errors}")
            if page_errors:
                raise AssertionError(f"Page errors: {page_errors}")
            if failed_requests:
                raise AssertionError(f"Failed browser requests: {failed_requests}")
            if unexpected_responses:
                raise AssertionError(f"Unexpected server responses: {unexpected_responses}")
            result = "passed"
        except Exception as exc:
            result = "failed"
            record_action(actions, "Unhandled certification failure", "failed", str(exc))
            screenshot(page, output_dir, sequence, "failure-state")
            raise
        finally:
            context.tracing.stop(path=output_dir / "playwright-trace.zip")
            context.close()
            browser.close()

    summary = {
        "result": result,
        "fixture": fixture,
        "viewport": VIEWPORT,
        "actions": actions,
        "shell_metrics": shell_metrics,
        "control_inventory": inventory,
        "browser_diagnostics": {
            "console_errors": console_errors,
            "console_warnings": console_warnings,
            "page_errors": page_errors,
            "failed_requests": failed_requests,
            "unexpected_responses": unexpected_responses,
        },
    }
    (output_dir / "certification-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "control-inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    write_report(output_dir, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
