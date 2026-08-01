from __future__ import annotations

import atexit
import os
import re
from contextlib import suppress
from pathlib import Path
from threading import Lock
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


class LinkedInPlaywrightBatchCaptureRequest(BaseModel):
    targets: list[LinkedInPlaywrightCaptureRequest] = Field(default_factory=list, max_length=25)


class LinkedInPlaywrightBatchCaptureResponse(BaseModel):
    captured_count: int
    captures: list[LinkedInCaptureResponse]


class LinkedInLoginRequired(RuntimeError):
    """Raised when LinkedIn asks the visible browser to authenticate.

    This must not reset/close the Playwright context. The whole point is to keep
    Chromium open so Rafael can log in, then retry the same batch capture with
    the persistent browser profile.
    """


LOGIN_REQUIRED_MESSAGE = (
    "LinkedIn login required. Log in in the opened Chromium window, "
    "then click Capture enabled again. JOLT kept the browser session open."
)


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
_CAPTURE_LOCK = Lock()


def _reset_browser_context() -> None:
    global _BROWSER_CONTEXT
    if _BROWSER_CONTEXT is not None:
        with suppress(Exception):
            _BROWSER_CONTEXT.close()
    _BROWSER_CONTEXT = None


def _stop_playwright() -> None:
    global _PLAYWRIGHT
    _reset_browser_context()
    if _PLAYWRIGHT is not None:
        with suppress(Exception):
            _PLAYWRIGHT.stop()
    _PLAYWRIGHT = None


atexit.register(_stop_playwright)


def _get_browser_context() -> Any:
    """Return one visible persistent browser context for the backend process.

    Multi-section capture must be backend-owned. The frontend must not create one
    HTTP request per target, because FastAPI may serve those requests from different
    threads and Playwright objects are not safe to hop between threads. The batch
    endpoint uses this context inside one locked request so Chromium stays visible
    while JOLT navigates through the enabled sections.
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
            _ = _BROWSER_CONTEXT.pages
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


def _page_needs_linkedin_login(page: Any) -> bool:
    """Detect login/checkpoint pages before JOLT tries to capture a section.

    LinkedIn may redirect profile/detail URLs to login, checkpoint, challenge,
    or authwall pages when the persistent browser profile has no active session.
    In that case the correct workflow is to stop the batch and let the user log
    in inside the already-open visible browser.
    """
    current_url = page.url.lower()
    if any(
        marker in current_url
        for marker in ("/login", "/checkpoint", "/uas/login", "authwall", "session_redirect")
    ):
        return True
    try:
        body_text = page.locator("body").inner_text(timeout=3_000).lower()
    except Exception:
        return False
    login_markers = (
        "sign in",
        "join linkedin",
        "join now",
        "email or phone",
        "password",
        "security verification",
        "let's do a quick security check",
        "verify your identity",
    )
    return any(marker in body_text for marker in login_markers)


def _capture_with_context(
    session: Session,
    context: Any,
    request: LinkedInPlaywrightCaptureRequest,
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

    page = context.pages[0] if context.pages else context.new_page()
    with suppress(Exception):
        page.bring_to_front()
    page.goto(request.url.strip(), wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(1_000)
    if _page_needs_linkedin_login(page):
        raise LinkedInLoginRequired(LOGIN_REQUIRED_MESSAGE)
    if request.wait_seconds > 0:
        page.wait_for_timeout(int(request.wait_seconds * 1000))
    with suppress(PlaywrightTimeoutError):
        page.wait_for_load_state("networkidle", timeout=8_000)
    if _page_needs_linkedin_login(page):
        raise LinkedInLoginRequired(LOGIN_REQUIRED_MESSAGE)
    final_url = page.url
    page_title = page.title() or title
    visible_text = page.locator("body").inner_text(timeout=10_000).strip()
    page.screenshot(path=str(screenshot_path), full_page=request.full_page_screenshot)

    notes = "\n".join(
        [
            "Captured by JOLT LinkedIn Command Center Playwright flow.",
            "Browser session is backend-owned for multi-section captures.",
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


def run_linkedin_playwright_capture(
    session: Session, request: LinkedInPlaywrightCaptureRequest
) -> LinkedInCaptureResponse:
    with _CAPTURE_LOCK:
        try:
            context = _get_browser_context()
            return _capture_with_context(session, context, request)
        except LinkedInLoginRequired as exc:
            # Keep Chromium open so the user can log in and retry.
            raise RuntimeError(LOGIN_REQUIRED_MESSAGE) from exc
        except Exception:
            _reset_browser_context()
            raise


def run_linkedin_playwright_batch_capture(
    session: Session, request: LinkedInPlaywrightBatchCaptureRequest
) -> LinkedInPlaywrightBatchCaptureResponse:
    captures: list[LinkedInCaptureResponse] = []
    targets = [target for target in request.targets if target.url.strip()]
    with _CAPTURE_LOCK:
        try:
            context = _get_browser_context()
            for target in targets:
                captures.append(_capture_with_context(session, context, target))
            return LinkedInPlaywrightBatchCaptureResponse(
                captured_count=len(captures),
                captures=captures,
            )
        except LinkedInLoginRequired as exc:
            # Keep Chromium open on the login/checkpoint page. The frontend will
            # show the 400 message, and the user can retry after authenticating.
            raise RuntimeError(LOGIN_REQUIRED_MESSAGE) from exc
        except Exception:
            _reset_browser_context()
            raise
