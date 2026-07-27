from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

from playwright.sync_api import Page, Route

CLASSIFIED_PATH = Path(__file__).with_name(
    "jolt-full-cycle-playwright-certification-classified.py"
)


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
    dialog.get_by_role("alert").filter(
        has_text="Unable to load application tasks."
    ).wait_for(timeout=30_000)
    dialog.get_by_role("button", name="Retry tasks", exact=True).wait_for()
    module.record_action(actions, "Show recoverable task-load error", "passed")

    page.unroute(task_pattern, fail_first_task_load)
    dialog.get_by_role("button", name="Retry tasks", exact=True).click()
    corrected_task = dialog.locator("li").filter(has_text="corrected").first
    corrected_task.wait_for(timeout=30_000)
    module.record_action(actions, "Recover task list with local retry", "passed")

    corrected_task.get_by_role("button", name="Edit task", exact=True).click()
    title_input = dialog.get_by_label("Task title")
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
                body=json.dumps(
                    {"detail": "Injected task validation failure for certification."}
                ),
            )
            return
        route.continue_()

    page.route(update_pattern, fail_first_task_update)
    dialog.get_by_role("button", name="Save task changes", exact=True).click()
    dialog.get_by_role("alert").filter(
        has_text="Injected task validation failure for certification."
    ).wait_for(timeout=30_000)
    if title_input.input_value() != recovered_title:
        raise AssertionError("Task edit form did not preserve the entered title after validation failure.")
    dialog.get_by_role("button", name="Save task changes", exact=True).wait_for()
    module.record_action(actions, "Preserve task edit after validation error", "passed")

    page.unroute(update_pattern, fail_first_task_update)
    dialog.get_by_role("button", name="Save task changes", exact=True).click()
    dialog.get_by_text(recovered_title, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Recover task save after validation error", "passed")

    page.reload(wait_until="networkidle")
    module.open_application(page, fixture)
    dialog = page.get_by_role("dialog", name=fixture["title"])
    dialog.get_by_role("tab", name="Tasks", exact=True).click()
    dialog.get_by_text(recovered_title, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Recovered task change persists after reload", "passed")
    page.screenshot(
        path=Path(
            "../artifacts/full-cycle-certification/evidence/screenshots/010-validation-retry-recovery.png"
        ),
        full_page=True,
    )


def main() -> int:
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
    return int(classified.main())


if __name__ == "__main__":
    raise SystemExit(main())
