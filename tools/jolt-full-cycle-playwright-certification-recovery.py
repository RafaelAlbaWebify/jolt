from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from playwright.sync_api import ConsoleMessage, Page, Route

from jolt.certification_isolation import assert_certification_backend

CLASSIFIED_PATH = Path(__file__).with_name("jolt-full-cycle-playwright-certification-classified.py")

EXPECTED_CONSOLE_ERRORS = {
    "Failed to load resource: the server responded with a status of 429 (Too Many Requests)": 1,
    "Failed to load resource: the server responded with a status of 422 (Unprocessable Entity)": 1,
}


def load_classified() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "jolt_full_cycle_classified_with_recovery", CLASSIFIED_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load classified certification from {CLASSIFIED_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise_task_recovery(
    module: ModuleType,
    page: Page,
    fixture: dict[str, str],
    actions: list[dict[str, str]],
) -> None:
    task_pattern = "**/api/applications/*/tasks"
    task_failure_sent = False

    def fail_first_task_load(route: Route) -> None:
        nonlocal task_failure_sent
        if not task_failure_sent and route.request.method == "GET":
            task_failure_sent = True
            route.fulfill(
                status=429,
                content_type="application/json",
                body=json.dumps({"detail": "Injected task-list retry certification."}),
            )
            return
        route.continue_()

    page.route(task_pattern, fail_first_task_load)
    page.reload(wait_until="networkidle")
    module.open_application(page, fixture)
    dialog = page.get_by_role("dialog", name=fixture["title"])
    dialog.get_by_role("tab", name="Tasks", exact=True).click()
    tasks_panel = dialog.locator("#application-panel-tasks")
    tasks_panel.get_by_role("alert").filter(has_text="Unable to load application tasks.").first.wait_for(
        timeout=30_000
    )
    tasks_panel.get_by_role("button", name="Retry tasks", exact=True).wait_for()
    module.record_action(actions, "Show recoverable task-load error", "passed")

    page.unroute(task_pattern, fail_first_task_load)
    tasks_panel.get_by_role("button", name="Retry tasks", exact=True).click()
    corrected_task = tasks_panel.locator("li").filter(has_text="corrected").first
    corrected_task.wait_for(timeout=30_000)
    module.record_action(actions, "Recover task list with local retry", "passed")

    corrected_task.get_by_role("button", name="Edit task", exact=True).click()
    title_input = tasks_panel.get_by_label("Task title")
    original_title = title_input.input_value()
    recovered_title = f"{original_title} validated"
    title_input.fill(recovered_title)

    update_pattern = "**/api/application-tasks/*/update"
    validation_failure_sent = False

    def fail_first_task_update(route: Route) -> None:
        nonlocal validation_failure_sent
        if not validation_failure_sent and route.request.method == "POST":
            validation_failure_sent = True
            route.fulfill(
                status=422,
                content_type="application/json",
                body=json.dumps({"detail": "Injected task validation failure for certification."}),
            )
            return
        route.continue_()

    page.route(update_pattern, fail_first_task_update)
    tasks_panel.get_by_role("button", name="Save task changes", exact=True).click()
    tasks_panel.get_by_role("alert").filter(
        has_text="Injected task validation failure for certification."
    ).first.wait_for(timeout=30_000)
    if title_input.input_value() != recovered_title:
        raise AssertionError(
            "Task edit form did not preserve the entered title after validation failure."
        )
    tasks_panel.get_by_role("button", name="Save task changes", exact=True).wait_for()
    module.record_action(actions, "Preserve task edit after validation error", "passed")

    page.unroute(update_pattern, fail_first_task_update)
    tasks_panel.get_by_role("button", name="Save task changes", exact=True).click()
    tasks_panel.get_by_text(recovered_title, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Recover task save after validation error", "passed")

    page.reload(wait_until="networkidle")
    module.open_application(page, fixture)
    dialog = page.get_by_role("dialog", name=fixture["title"])
    dialog.get_by_role("tab", name="Tasks", exact=True).click()
    dialog.locator("#application-panel-tasks").get_by_text(recovered_title, exact=True).wait_for(
        timeout=30_000
    )
    module.record_action(actions, "Recovered task change persists after reload", "passed")
    page.screenshot(
        path=Path(
            "../artifacts/full-cycle-certification/evidence/screenshots/010-validation-retry-recovery.png"
        ),
        full_page=True,
    )


def main() -> int:
    certification_database = assert_certification_backend()
    print(
        json.dumps(
            {
                "certification_database_isolation": "verified",
                "database_path": str(certification_database),
            },
            indent=2,
        )
    )

    classified = load_classified()
    restart = classified.load_restart()
    original_restart_and_verify = restart.restart_and_verify

    def recovery_then_restart(
        module: ModuleType,
        page: Page,
        fixture: dict[str, str],
        actions: list[dict[str, str]],
    ) -> None:
        exercise_task_recovery(module, page, fixture, actions)
        original_restart_and_verify(module, page, fixture, actions)

    restart.restart_and_verify = recovery_then_restart
    classified.load_restart = lambda: restart

    remaining_expected = dict(EXPECTED_CONSOLE_ERRORS)
    original_page_on = Page.on

    def filtered_page_on(
        self: Page,
        event: str,
        handler: Callable[[Any], Any],
    ) -> Page:
        if event != "console":
            return original_page_on(self, event, handler)

        def filtered_handler(message: ConsoleMessage) -> Any:
            remaining = remaining_expected.get(message.text, 0)
            if message.type == "error" and remaining > 0:
                remaining_expected[message.text] = remaining - 1
                return None
            return handler(message)

        return original_page_on(self, event, filtered_handler)

    Page.on = filtered_page_on  # type: ignore[method-assign]
    try:
        return int(classified.main())
    finally:
        Page.on = original_page_on  # type: ignore[method-assign]


if __name__ == "__main__":
    raise SystemExit(main())
