from __future__ import annotations

import importlib.util
import time
from datetime import datetime, timedelta
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


def require_rendered(dialog_text: str, fragments: tuple[str, ...], subject: str) -> None:
    missing = [fragment for fragment in fragments if fragment not in dialog_text]
    if missing:
        raise AssertionError(f"{subject} is missing rendered evidence: {missing}")


def exercise_task_cycle(
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
    page.get_by_label("Task title").fill(f"{task_title} cancelled correction")
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

    with page.expect_response(
        lambda response: response.request.method == "POST" and response.url.endswith("/reopen")
    ) as response_info:
        corrected_item.get_by_role("button", name="Reopen", exact=True).click()
    if response_info.value.status >= 400:
        raise AssertionError(f"Task reopen returned HTTP {response_info.value.status}")
    corrected_item.get_by_role("button", name="Complete", exact=True).wait_for(timeout=30_000)
    page.wait_for_load_state("networkidle")
    module.record_action(actions, "Reopen application task", "passed")

    page.reload(wait_until="networkidle")
    module.open_application(page, fixture)
    page.get_by_role("tab", name="Tasks", exact=True).click()
    page.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Task persists after reload", "passed")

    page.get_by_role("tab", name="Timeline", exact=True).click()
    page.get_by_role("heading", name="Timeline", exact=True).wait_for(timeout=30_000)
    rendered = page.get_by_role("dialog", name=fixture["title"]).inner_text()
    require_rendered(
        rendered,
        (
            "Task Updated",
            task_title,
            corrected,
            "Initial certification task notes.",
            "Corrected certification task notes.",
        ),
        "Task correction timeline",
    )
    module.record_action(actions, "Task correction visible in timeline", "passed")


def exercise_contact_cycle(
    module: ModuleType,
    page: Page,
    fixture: dict[str, str],
    actions: list[dict[str, str]],
) -> None:
    page.get_by_role("tab", name="Contacts", exact=True).click()
    page.get_by_role("heading", name="Contacts", exact=True).wait_for(timeout=30_000)
    stamp = time.strftime("%H%M%S")
    name = f"Certification Contact {stamp}"
    corrected = f"{name} Corrected"
    page.get_by_label("Name").fill(name)
    page.get_by_label("Role").fill("Recruiter")
    page.get_by_label("Company").fill("Certification Systems")
    page.get_by_label("Email").fill(f"certification-{stamp}@example.test")
    page.get_by_label("Notes").fill("Initial contact notes.")
    page.get_by_role("button", name="Add contact", exact=True).click()
    page.get_by_text(name, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Create application contact", "passed")

    item = page.locator("li").filter(has_text=name)
    item.get_by_role("button", name="Edit contact", exact=True).click()
    page.get_by_label("Name").fill(f"{name} Cancelled")
    page.get_by_role("button", name="Cancel edit", exact=True).click()
    page.get_by_text(name, exact=True).wait_for()
    module.record_action(actions, "Cancel contact edit", "passed")

    item.get_by_role("button", name="Edit contact", exact=True).click()
    page.get_by_label("Name").fill(corrected)
    page.get_by_label("Role").fill("Senior recruiter")
    page.get_by_label("Notes").fill("Corrected contact notes.")
    page.get_by_role("button", name="Save contact changes", exact=True).click()
    page.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Edit application contact", "passed")

    page.reload(wait_until="networkidle")
    module.open_application(page, fixture)
    page.get_by_role("tab", name="Contacts", exact=True).click()
    page.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Contact persists after reload", "passed")

    page.get_by_role("tab", name="Timeline", exact=True).click()
    rendered = page.get_by_role("dialog", name=fixture["title"]).inner_text()
    require_rendered(
        rendered,
        ("Contact Updated", name, corrected, "Recruiter", "Senior recruiter"),
        "Contact correction timeline",
    )
    module.record_action(actions, "Contact correction visible in timeline", "passed")


def exercise_document_cycle(
    module: ModuleType,
    page: Page,
    fixture: dict[str, str],
    actions: list[dict[str, str]],
) -> None:
    page.get_by_role("tab", name="Documents", exact=True).click()
    page.get_by_role("heading", name="Documents", exact=True).wait_for(timeout=30_000)
    stamp = time.strftime("%H%M%S")
    title = f"Certification Resume {stamp}"
    corrected = f"{title} Corrected"
    page.get_by_label("Title").fill(title)
    page.get_by_label("Local file path").fill(f"C:/certification/{stamp}/resume.pdf")
    page.get_by_label("Source URL").fill(f"https://example.test/documents/{stamp}")
    page.get_by_label("Notes").fill("Initial document notes.")
    page.get_by_role("button", name="Add document", exact=True).click()
    page.get_by_text(title, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Create application document", "passed")

    item = page.locator("li").filter(has_text=title)
    item.get_by_role("button", name="Edit document", exact=True).click()
    page.get_by_label("Title").fill(f"{title} Cancelled")
    page.get_by_role("button", name="Cancel edit", exact=True).click()
    page.get_by_text(title, exact=True).wait_for()
    module.record_action(actions, "Cancel document edit", "passed")

    item.get_by_role("button", name="Edit document", exact=True).click()
    page.get_by_label("Title").fill(corrected)
    page.get_by_label("Status").select_option("ready")
    page.get_by_label("Notes").fill("Corrected document notes.")
    page.get_by_role("button", name="Save document changes", exact=True).click()
    page.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Edit application document", "passed")

    page.reload(wait_until="networkidle")
    module.open_application(page, fixture)
    page.get_by_role("tab", name="Documents", exact=True).click()
    page.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Document persists after reload", "passed")

    page.get_by_role("tab", name="Timeline", exact=True).click()
    rendered = page.get_by_role("dialog", name=fixture["title"]).inner_text()
    require_rendered(
        rendered,
        ("Document Updated", title, corrected, "draft", "ready"),
        "Document correction timeline",
    )
    module.record_action(actions, "Document correction visible in timeline", "passed")


def schedule_interview(page: Page, scheduled_at: str, location: str, participant: str) -> None:
    page.get_by_label("Date and time").fill(scheduled_at)
    page.get_by_label("Format or location").fill(location)
    page.get_by_label("Participants").fill(participant)
    page.get_by_label("Preparation notes").fill("Initial interview preparation notes.")
    page.get_by_role("button", name="Schedule interview", exact=True).click()


def exercise_interview_cycle(
    module: ModuleType,
    page: Page,
    fixture: dict[str, str],
    actions: list[dict[str, str]],
) -> None:
    page.get_by_role("tab", name="Interviews", exact=True).click()
    page.get_by_role("heading", name="Interviews", exact=True).wait_for(timeout=30_000)
    first_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    schedule_interview(page, first_time, "Teams", "Initial Recruiter")
    first = page.locator("li").filter(has_text="recruiter screen").first
    first.wait_for(timeout=30_000)
    module.record_action(actions, "Schedule application interview", "passed")

    first.get_by_role("button", name="Edit interview", exact=True).click()
    page.get_by_label("Format or location").fill("Cancelled correction")
    page.get_by_role("button", name="Cancel edit", exact=True).click()
    first.get_by_text("Teams", exact=True).wait_for()
    module.record_action(actions, "Cancel interview edit", "passed")

    first.get_by_role("button", name="Edit interview", exact=True).click()
    page.get_by_label("Interview type").select_option("technical_interview")
    page.get_by_label("Format or location").fill("Teams corrected")
    page.get_by_label("Participants").fill("Technical Panel")
    page.get_by_label("Outcome notes").fill("Corrected interview outcome notes.")
    page.get_by_role("button", name="Save interview changes", exact=True).click()
    corrected_first = page.locator("li").filter(has_text="technical interview").first
    corrected_first.wait_for(timeout=30_000)
    module.record_action(actions, "Edit application interview", "passed")

    corrected_first.get_by_role("button", name="Complete", exact=True).click()
    corrected_first.get_by_text("completed", exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Complete application interview", "passed")

    second_time = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    schedule_interview(page, second_time, "Phone", "Second Recruiter")
    scheduled_items = page.locator("li").filter(has_text="recruiter screen")
    second = scheduled_items.last
    second.wait_for(timeout=30_000)
    second.get_by_role("button", name="Cancel", exact=True).click()
    second.get_by_text("cancelled", exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Cancel application interview", "passed")

    page.reload(wait_until="networkidle")
    module.open_application(page, fixture)
    page.get_by_role("tab", name="Interviews", exact=True).click()
    page.get_by_text("technical interview", exact=True).wait_for(timeout=30_000)
    page.get_by_text("completed", exact=True).first.wait_for(timeout=30_000)
    page.get_by_text("cancelled", exact=True).first.wait_for(timeout=30_000)
    module.record_action(actions, "Interview states persist after reload", "passed")

    page.get_by_role("tab", name="Timeline", exact=True).click()
    rendered = page.get_by_role("dialog", name=fixture["title"]).inner_text()
    require_rendered(
        rendered,
        (
            "Interview Updated",
            "recruiter_screen",
            "technical_interview",
            "Teams",
            "Teams corrected",
            "Interview Completed",
            "Interview Cancelled",
        ),
        "Interview correction timeline",
    )
    module.record_action(actions, "Interview lifecycle visible in timeline", "passed")


def exercise_application_resources(
    module: ModuleType,
    page: Page,
    fixture: dict[str, str],
    actions: list[dict[str, str]],
) -> None:
    exercise_task_cycle(module, page, fixture, actions)
    exercise_contact_cycle(module, page, fixture, actions)
    exercise_document_cycle(module, page, fixture, actions)
    exercise_interview_cycle(module, page, fixture, actions)
    page.screenshot(
        path=Path("../artifacts/full-cycle-certification/evidence/screenshots/008-all-resource-timeline.png"),
        full_page=True,
    )


def main() -> int:
    module = load_certification()
    module.exercise_tasks = lambda page, fixture, actions: exercise_application_resources(
        module, page, fixture, actions
    )
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
