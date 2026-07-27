from __future__ import annotations

import importlib.util
import time
from pathlib import Path
from types import ModuleType

from playwright.sync_api import Page


MODULE_PATH = Path(__file__).with_name("jolt-full-cycle-playwright-certification.py")


def load_certification() -> ModuleType:
    spec = importlib.util.spec_from_file_location("jolt_full_cycle_certification", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load certification module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise_tasks(
    module: ModuleType,
    page: Page,
    fixture: dict[str, str],
    actions: list[dict[str, str]],
) -> None:
    module.open_application(page, fixture)
    page.get_by_role("tab", name="Tasks", exact=True).click()
    page.get_by_role("heading", name="Tasks", exact=True).wait_for(timeout=30_000)

    task_title = f"Certification task {time.strftime('%H%M%S')}"
    page.get_by_label("Task title").fill(task_title)
    page.get_by_label("Notes").fill("Initial certification task notes.")
    page.get_by_role("button", name="Add task", exact=True).click()
    page.get_by_text(task_title, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Create application task", "passed")

    item = page.locator("li").filter(has_text=task_title)
    item.get_by_role("button", name="Edit task", exact=True).click()
    page.get_by_label("Task title").fill(f"{task_title} corrected")
    page.get_by_role("button", name="Cancel edit", exact=True).click()
    page.get_by_text(task_title, exact=True).wait_for()
    module.record_action(actions, "Cancel task edit", "passed")

    item.get_by_role("button", name="Edit task", exact=True).click()
    corrected = f"{task_title} corrected"
    page.get_by_label("Task title").fill(corrected)
    page.get_by_label("Notes").fill("Corrected certification task notes.")
    page.get_by_role("button", name="Save task changes", exact=True).click()
    page.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Edit application task", "passed")

    corrected_item = page.locator("li").filter(has_text=corrected)
    corrected_item.get_by_role("button", name="Complete", exact=True).click()
    corrected_item.get_by_role("button", name="Reopen", exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Complete application task", "passed")
    corrected_item.get_by_role("button", name="Reopen", exact=True).click()
    corrected_item.get_by_role("button", name="Complete", exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Reopen application task", "passed")

    page.reload(wait_until="networkidle")
    module.open_application(page, fixture)
    page.get_by_role("tab", name="Tasks", exact=True).click()
    page.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Task persists after reload", "passed")

    page.get_by_role("tab", name="Timeline", exact=True).click()
    page.get_by_role("heading", name="Timeline", exact=True).wait_for(timeout=30_000)
    rendered_timeline = page.get_by_role("dialog", name=fixture["title"]).inner_text()
    required_fragments = (
        "Task Updated",
        task_title,
        corrected,
        "Initial certification task notes.",
        "Corrected certification task notes.",
    )
    missing = [fragment for fragment in required_fragments if fragment not in rendered_timeline]
    if missing:
        raise AssertionError(f"Task correction timeline is missing rendered evidence: {missing}")
    module.record_action(actions, "Task correction visible in timeline", "passed")


def main() -> int:
    module = load_certification()
    module.exercise_tasks = lambda page, fixture, actions: exercise_tasks(
        module, page, fixture, actions
    )
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
