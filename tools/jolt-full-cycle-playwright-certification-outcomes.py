from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from playwright.sync_api import Locator, Page

RESOURCES_PATH = Path(__file__).with_name(
    "jolt-full-cycle-playwright-certification-resources.py"
)


def load_resources() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "jolt_full_cycle_resources_with_outcomes", RESOURCES_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load resource certification from {RESOURCES_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def open_workflow(
    page: Page,
    module: ModuleType,
    fixture: dict[str, str],
    status: str,
) -> Locator:
    dialog = page.get_by_role("dialog", name=fixture["title"])
    if not dialog.is_visible():
        module.open_application(page, fixture)
        dialog = page.get_by_role("dialog", name=fixture["title"])
    dialog.wait_for(timeout=30_000)
    dialog.get_by_role("tab", name="Overview", exact=True).click()
    toggle = dialog.get_by_role(
        "button", name=f"Manage application · {status.replace('_', ' ')}", exact=True
    )
    toggle.click()
    dialog.get_by_role(
        "heading", name=status.replace("_", " "), exact=True
    ).wait_for(timeout=30_000)
    return dialog


def exercise_outcome_cycle(
    module: ModuleType,
    page: Page,
    fixture: dict[str, str],
    actions: list[dict[str, str]],
) -> None:
    dialog = open_workflow(page, module, fixture, "submitted")
    dialog.get_by_label("Activity or correction notes").fill(
        "Certification rejection outcome before reopening."
    )
    dialog.get_by_label("Outcome").select_option("rejected_by_employer")
    with page.expect_response(
        lambda response: response.request.method == "POST"
        and response.url.endswith("/outcomes")
    ) as response_info:
        dialog.get_by_role("button", name="Record final outcome", exact=True).click()
    if response_info.value.status >= 400:
        raise AssertionError(
            f"Final outcome returned HTTP {response_info.value.status}"
        )
    dialog.get_by_text("Final outcome: rejected by employer", exact=True).wait_for(
        timeout=30_000
    )
    module.record_action(actions, "Record final application outcome", "passed")

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(750)
    page.reload(wait_until="networkidle")
    dialog = open_workflow(page, module, fixture, "rejected")
    dialog.get_by_text("Final outcome: rejected by employer", exact=True).wait_for(
        timeout=30_000
    )
    module.record_action(actions, "Outcome persists after reload", "passed")

    dialog.get_by_label("Activity or correction notes").fill(
        "Certification reopening correction."
    )
    dialog.get_by_label("Stage").select_option("recruiter_screen")
    with page.expect_response(
        lambda response: response.request.method == "POST"
        and response.url.endswith("/transitions")
    ) as response_info:
        dialog.get_by_role("button", name="Save stage", exact=True).click()
    if response_info.value.status >= 400:
        raise AssertionError(
            f"Outcome reopening returned HTTP {response_info.value.status}"
        )
    dialog.get_by_role("heading", name="recruiter screen", exact=True).wait_for(
        timeout=30_000
    )
    module.record_action(actions, "Reopen application from final outcome", "passed")

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(750)
    page.reload(wait_until="networkidle")
    dialog = open_workflow(page, module, fixture, "recruiter_screen")
    dialog.get_by_role("heading", name="recruiter screen", exact=True).wait_for(
        timeout=30_000
    )
    dialog.get_by_text("Final outcome: rejected by employer", exact=True).wait_for(
        state="detached", timeout=30_000
    )
    history = dialog.locator("details.application-event-history")
    history.locator("summary").click()
    rendered = history.inner_text()
    required = (
        "rejected by employer",
        "Certification rejection outcome before reopening.",
        "Certification reopening correction.",
    )
    missing = [fragment for fragment in required if fragment not in rendered]
    if missing:
        raise AssertionError(f"Outcome reopening history is missing evidence: {missing}")
    module.record_action(actions, "Reopened outcome history persists", "passed")
    page.screenshot(
        path=Path(
            "../artifacts/full-cycle-certification/evidence/screenshots/009-outcome-reopened-history.png"
        ),
        full_page=True,
    )


def main() -> int:
    resources = load_resources()
    runner = resources.load_runner()
    runner.exercise_contact_cycle = (
        lambda module, page, fixture, actions: resources.contact_cycle(
            runner, module, page, fixture, actions
        )
    )
    runner.exercise_document_cycle = (
        lambda module, page, fixture, actions: resources.document_cycle(
            runner, module, page, fixture, actions
        )
    )
    runner.exercise_interview_cycle = (
        lambda module, page, fixture, actions: resources.interview_cycle(
            runner, module, page, fixture, actions
        )
    )
    original_resources = runner.exercise_application_resources

    def resources_and_outcome(
        module: ModuleType,
        page: Page,
        fixture: dict[str, str],
        actions: list[dict[str, str]],
    ) -> None:
        original_resources(module, page, fixture, actions)
        exercise_outcome_cycle(module, page, fixture, actions)

    runner.exercise_application_resources = resources_and_outcome
    original_reload = Page.reload

    def settled_reload(self: Page, *args: Any, **kwargs: Any) -> Any:
        self.wait_for_load_state("networkidle")
        self.wait_for_timeout(750)
        return original_reload(self, *args, **kwargs)

    Page.reload = settled_reload  # type: ignore[method-assign]
    return int(runner.main())


if __name__ == "__main__":
    raise SystemExit(main())