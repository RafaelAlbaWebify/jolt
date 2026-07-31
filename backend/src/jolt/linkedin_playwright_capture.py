from __future__ import annotations

import atexit
import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from jolt.linkedin_command_center import (
    LinkedInCaptureCategory,
    LinkedInCaptureRequest,
    LinkedInCaptureResponse,
    create_linkedin_capture,
)


class LinkedInPlaywrightCaptureRequest(BaseModel):
    category: LinkedInCaptureCategory
    title: str = Field(default="", max_length=200)
    url: str = Field(min_length=1, max_length=4000)
    wait_seconds: float = Field(default=4.0, ge=0.0, le=60.0)
    full_page_screenshot: bool = False


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return slug[:80] or "linkedin-capture"


def _downloads_dir() -> Path:
    profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    downloads = profile / "Downloads"
    return downloads if downloads.exists() else Path.cwd()


def _capture_root() -> Path:
    root = _downloads_dir() / "JOLT_LINKEDIN_CAPTURES"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _browser_profile_dir() -> Path:
    root = Path.cwd() / "backend" / "data" / "playwright" / "linkedin-command-center"
    root.mkdir(parents=True, exist_ok=True)
    return root


_PLAYWRIGHT: Any | None = None
_BROWSER_CONTEXT: Any | None = None


def _reset_browser_context() -> None:
    global _BROWSER_CONTEXT
    if _BROWSER_CONTEXT is not None:
        try:
            _BROWSER_CONTEXT.close()
        except Exception:
            pass
    _BROWSER_CONTEXT = None


def _stop_playwright() -> None:
    global _PLAYWRIGHT
    _reset_browser_context()
    if _PLAYWRIGHT is not None:
        try:
            _PLAYWRIGHT.stop()
        except Exception:
            pass
    _PLAYWRIGHT = None


atexit.register(_stop_playwright)


def _get_browser_context() -> Any:
    """Return one visible persistent browser context for the backend process.

    The earlier implementation opened and closed Chromium for every target. That made
    multi-section capture look like Chromium was flashing or hiding repeatedly. Keeping
    one context alive lets `Capture enabled` navigate the same visible browser through
    the configured LinkedIn sections.
    """
    global _PLAYWRIGHT, _BROWSER_CONTEXT
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - depends on local dev dependency install
        raise RuntimeError(
            "Playwright is not available. Run `uv --project backend sync --dev` and install browsers."
        ) from exc

    if _PLAYWRIGHT is None:
        _PLAYWRIGHT = sync_playwright().start()

    if _BROWSER_CONTEXT is not None:
        try:
            _BROWSER_CONTEXT.pages
            return _BROWSER_CONTEXT
        except Exception:
            _BROWSER_CONTEXT = None

    _BROWSER_CONTEXT = _PLAYWRIGHT.chromium.launch_persistent_context(
        user_data_dir=str(_browser_profile_dir()),
        headless=False,
        no_viewport=True,
        args=["--start-maximized"],
    )
    return _BROWSER_CONTEXT


def run_linkedin_playwright_capture(
    session: Session, request: LinkedInPlaywrightCaptureRequest
) -> LinkedInCaptureResponse:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except Exception as exc:  # pragma: no cover - depends on local dev dependency install
        raise RuntimeError(
            "Playwright is not available. Run `uv --project backend sync --dev` and install browsers."
        ) from exc

    capture_root = _capture_root()
    title = request.title.strip() or "LinkedIn capture"
    screenshot_path = capture_root / f"{_safe_slug(title)}.png"

    final_url = request.url.strip()
    page_title = title
    visible_text = ""

    context = _get_browser_context()
    page = context.pages[0] if context.pages else context.new_page()
    try:
        page.bring_to_front()
    except Exception:
        pass
    try:
        page.goto(request.url.strip(), wait_until="domcontentloaded", timeout=60_000)
        if request.wait_seconds > 0:
            page.wait_for_timeout(int(request.wait_seconds * 1000))
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except PlaywrightTimeoutError:
            pass
        final_url = page.url
        page_title = page.title() or title
        visible_text = page.locator("body").inner_text(timeout=10_000).strip()
        page.screenshot(path=str(screenshot_path), full_page=request.full_page_screenshot)
    except Exception:
        _reset_browser_context()
        raise

    notes = "\n".join(
        [
            "Captured by JOLT LinkedIn Command Center Playwright flow.",
            "Browser session kept open for multi-section captures.",
            f"Page title: {page_title}",
            f"Final URL: {final_url}",
            f"Screenshot: {screenshot_path}",
        ]
    )
    return create_linkedin_capture(
        session,
        LinkedInCaptureRequest(
            category=request.category,
            title=title,
            source_url=final_url,
            visible_text=visible_text,
            notes=notes,
        ),
    )
