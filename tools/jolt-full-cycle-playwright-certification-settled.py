from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from playwright.sync_api import Page


RESOURCES_PATH = Path(__file__).with_name(
    "jolt-full-cycle-playwright-certification-resources.py"
)


def load_resources() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "jolt_full_cycle_resources", RESOURCES_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load resource certification from {RESOURCES_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    resources = load_resources()
    original_reload = Page.reload

    def settled_reload(self: Page, *args: Any, **kwargs: Any) -> Any:
        self.wait_for_load_state("networkidle")
        self.wait_for_timeout(750)
        return original_reload(self, *args, **kwargs)

    Page.reload = settled_reload  # type: ignore[method-assign]
    return int(resources.main())


if __name__ == "__main__":
    raise SystemExit(main())
