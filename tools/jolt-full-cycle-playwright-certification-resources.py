from __future__ import annotations

import importlib.util
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType

from playwright.sync_api import Locator, Page

RUNNER_PATH = Path(__file__).with_name("jolt-full-cycle-playwright-certification-runner.py")


def load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("jolt_full_cycle_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load certification runner from {RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dialog_for(page: Page, fixture: dict[str, str]) -> Locator:
    dialog = page.get_by_role("dialog", name=fixture["title"])
    dialog.wait_for(timeout=30_000)
    return dialog


def contact_cycle(
    runner: ModuleType,
    module: ModuleType,
    page: Page,
    fixture: dict[str, str],
    actions: list[dict[str, str]],
) -> None:
    dialog = dialog_for(page, fixture)
    dialog.get_by_role("tab", name="Contacts", exact=True).click()
    dialog.get_by_role("heading", name="Contacts", exact=True).wait_for(timeout=30_000)
    stamp = time.strftime("%H%M%S")
    name = f"Certification Contact {stamp}"
    corrected = f"{name} Corrected"
    dialog.get_by_role("textbox", name="Name", exact=True).fill(name)
    dialog.get_by_role("textbox", name="Role", exact=True).fill("Recruiter")
    dialog.get_by_role("textbox", name="Company", exact=True).fill("Certification Systems")
    dialog.get_by_role("textbox", name="Email", exact=True).fill(
        f"certification-{stamp}@example.test"
    )
    dialog.get_by_role("textbox", name="Notes", exact=True).fill("Initial contact notes.")
    dialog.get_by_role("button", name="Add contact", exact=True).click()
    dialog.get_by_text(name, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Create application contact", "passed")

    item = dialog.locator("li").filter(has_text=name)
    item.get_by_role("button", name="Edit contact", exact=True).click()
    dialog.get_by_role("textbox", name="Name", exact=True).fill(f"{name} Cancelled")
    dialog.get_by_role("button", name="Cancel edit", exact=True).click()
    dialog.get_by_text(name, exact=True).wait_for()
    module.record_action(actions, "Cancel contact edit", "passed")

    item.get_by_role("button", name="Edit contact", exact=True).click()
    dialog.get_by_role("textbox", name="Name", exact=True).fill(corrected)
    dialog.get_by_role("textbox", name="Role", exact=True).fill("Senior recruiter")
    dialog.get_by_role("textbox", name="Notes", exact=True).fill("Corrected contact notes.")
    dialog.get_by_role("button", name="Save contact changes", exact=True).click()
    dialog.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Edit application contact", "passed")

    page.reload(wait_until="networkidle")
    module.open_application(page, fixture)
    dialog = dialog_for(page, fixture)
    dialog.get_by_role("tab", name="Contacts", exact=True).click()
    dialog.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Contact persists after reload", "passed")

    dialog.get_by_role("tab", name="Timeline", exact=True).click()
    runner.require_rendered(
        dialog.inner_text(),
        ("Contact Updated", name, corrected, "Recruiter", "Senior recruiter"),
        "Contact correction timeline",
    )
    module.record_action(actions, "Contact correction visible in timeline", "passed")


def document_cycle(
    runner: ModuleType,
    module: ModuleType,
    page: Page,
    fixture: dict[str, str],
    actions: list[dict[str, str]],
) -> None:
    dialog = dialog_for(page, fixture)
    dialog.get_by_role("tab", name="Documents", exact=True).click()
    dialog.get_by_role("heading", name="Documents", exact=True).wait_for(timeout=30_000)
    stamp = time.strftime("%H%M%S")
    title = f"Certification Resume {stamp}"
    corrected = f"{title} Corrected"
    dialog.get_by_role("textbox", name="Title", exact=True).fill(title)
    dialog.get_by_role("textbox", name="Source URL", exact=True).fill(
        f"https://example.test/documents/{stamp}"
    )
    dialog.get_by_role("textbox", name="Notes", exact=True).fill("Initial document notes.")

    stored_filename = f"certification-resume-{stamp}.txt"
    with tempfile.TemporaryDirectory() as temporary_directory:
        upload_path = Path(temporary_directory) / stored_filename
        upload_path.write_text(
            f"JOLT full-cycle certification resume {stamp}.",
            encoding="utf-8",
        )
        dialog.get_by_label("File", exact=True).set_input_files(str(upload_path))
        dialog.get_by_role("button", name="Add document", exact=True).click()

        dialog.get_by_text(title, exact=True).wait_for(timeout=30_000)
        dialog.get_by_text(
            f"Stored in JOLT: {stored_filename}",
            exact=False,
        ).wait_for(timeout=30_000)
    item = dialog.locator("li").filter(has_text=title)
    item.get_by_role("link", name="Download file", exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Create application document with stored file", "passed")

    item.get_by_role("button", name="Edit document", exact=True).click()
    dialog.get_by_role("textbox", name="Title", exact=True).fill(f"{title} Cancelled")
    dialog.get_by_role("button", name="Cancel edit", exact=True).click()
    dialog.get_by_text(title, exact=True).wait_for()
    module.record_action(actions, "Cancel document edit", "passed")

    item.get_by_role("button", name="Edit document", exact=True).click()
    dialog.get_by_role("textbox", name="Title", exact=True).fill(corrected)
    dialog.get_by_role("combobox", name="Status", exact=True).select_option("ready")
    dialog.get_by_role("textbox", name="Notes", exact=True).fill("Corrected document notes.")
    dialog.get_by_role("button", name="Save document changes", exact=True).click()
    dialog.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Edit application document", "passed")

    page.reload(wait_until="networkidle")
    module.open_application(page, fixture)
    dialog = dialog_for(page, fixture)
    dialog.get_by_role("tab", name="Documents", exact=True).click()
    dialog.get_by_text(corrected, exact=True).wait_for(timeout=30_000)
    dialog.get_by_text(
        f"Stored in JOLT: {stored_filename}",
        exact=False,
    ).wait_for(timeout=30_000)
    persisted_item = dialog.locator("li").filter(has_text=corrected)
    persisted_item.get_by_role(
        "link",
        name="Download file",
        exact=True,
    ).wait_for(timeout=30_000)
    module.record_action(
        actions,
        "Document and stored file persist after reload",
        "passed",
    )

    dialog.get_by_role("tab", name="Timeline", exact=True).click()
    runner.require_rendered(
        dialog.inner_text(),
        ("Document Updated", title, corrected, "draft", "ready"),
        "Document correction timeline",
    )
    module.record_action(actions, "Document correction visible in timeline", "passed")


def schedule_interview(
    dialog: Locator,
    scheduled_at: str,
    location: str,
    participant: str,
) -> None:
    dialog.get_by_role("textbox", name="Date and time", exact=True).fill(scheduled_at)
    dialog.get_by_role("textbox", name="Format or location", exact=True).fill(location)
    dialog.get_by_role("textbox", name="Participants", exact=True).fill(participant)
    dialog.get_by_role("textbox", name="Preparation notes", exact=True).fill(
        "Initial interview preparation notes."
    )
    dialog.get_by_role("button", name="Schedule interview", exact=True).click()


def interview_cycle(
    runner: ModuleType,
    module: ModuleType,
    page: Page,
    fixture: dict[str, str],
    actions: list[dict[str, str]],
) -> None:
    dialog = dialog_for(page, fixture)
    dialog.get_by_role("tab", name="Interviews", exact=True).click()
    dialog.get_by_role("heading", name="Interviews", exact=True).wait_for(timeout=30_000)
    first_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    schedule_interview(dialog, first_time, "Teams", "Initial Recruiter")
    first = dialog.locator("li").filter(has_text="recruiter screen").first
    first.wait_for(timeout=30_000)
    module.record_action(actions, "Schedule application interview", "passed")

    first.get_by_role("button", name="Edit interview", exact=True).click()
    dialog.get_by_role("textbox", name="Format or location", exact=True).fill(
        "Cancelled correction"
    )
    dialog.get_by_role("button", name="Cancel edit", exact=True).click()
    first.get_by_text("Teams", exact=True).wait_for()
    module.record_action(actions, "Cancel interview edit", "passed")

    first.get_by_role("button", name="Edit interview", exact=True).click()
    dialog.get_by_role("combobox", name="Interview type", exact=True).select_option(
        "technical_interview"
    )
    dialog.get_by_role("textbox", name="Format or location", exact=True).fill("Teams corrected")
    dialog.get_by_role("textbox", name="Participants", exact=True).fill("Technical Panel")
    dialog.get_by_role("textbox", name="Outcome notes", exact=True).fill(
        "Corrected interview outcome notes."
    )
    dialog.get_by_role("button", name="Save interview changes", exact=True).click()
    corrected_first = dialog.locator("li").filter(has_text="technical interview").first
    corrected_first.wait_for(timeout=30_000)
    module.record_action(actions, "Edit application interview", "passed")

    corrected_first.get_by_role("button", name="Complete", exact=True).click()
    corrected_first.get_by_text("completed", exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Complete application interview", "passed")

    second_time = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    schedule_interview(dialog, second_time, "Phone", "Second Recruiter")
    second = dialog.locator("li").filter(has_text="recruiter screen").last
    second.wait_for(timeout=30_000)
    second.get_by_role("button", name="Cancel", exact=True).click()
    second.get_by_text("cancelled", exact=True).wait_for(timeout=30_000)
    module.record_action(actions, "Cancel application interview", "passed")

    page.reload(wait_until="networkidle")
    module.open_application(page, fixture)
    dialog = dialog_for(page, fixture)
    dialog.get_by_role("tab", name="Interviews", exact=True).click()
    dialog.get_by_text("technical interview", exact=True).wait_for(timeout=30_000)
    dialog.get_by_text("completed", exact=True).first.wait_for(timeout=30_000)
    dialog.get_by_text("cancelled", exact=True).first.wait_for(timeout=30_000)
    module.record_action(actions, "Interview states persist after reload", "passed")

    dialog.get_by_role("tab", name="Timeline", exact=True).click()
    runner.require_rendered(
        dialog.inner_text(),
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


def main() -> int:
    runner = load_runner()
    runner.exercise_contact_cycle = lambda module, page, fixture, actions: contact_cycle(
        runner, module, page, fixture, actions
    )
    runner.exercise_document_cycle = lambda module, page, fixture, actions: document_cycle(
        runner, module, page, fixture, actions
    )
    runner.exercise_interview_cycle = lambda module, page, fixture, actions: interview_cycle(
        runner, module, page, fixture, actions
    )
    return int(runner.main())


if __name__ == "__main__":
    raise SystemExit(main())
