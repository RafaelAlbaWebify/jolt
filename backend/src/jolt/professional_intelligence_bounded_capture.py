from __future__ import annotations

import atexit
from contextlib import suppress
from pathlib import Path
from threading import Lock
from types import TracebackType

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright
from sqlalchemy.orm import Session

from jolt.professional_intelligence_capture_runs import (
    ProfessionalCaptureOptions,
    ProfessionalCaptureRunResponse,
    get_professional_capture_run,
)
from jolt.professional_intelligence_records import ProfessionalCaptureRun
from jolt.professional_intelligence_supervised_capture import (
    CapturedProfessionalPage,
    start_professional_supervised_capture,
)

_ITEM_SELECTORS = (
    "[data-job-id]",
    "li.jobs-search-results__list-item",
    ".reusable-search__result-container",
    "article",
)
_LOGIN_URL_MARKERS = (
    "/login",
    "/checkpoint",
    "/uas/login",
    "authwall",
    "session_redirect",
    "/signup",
)
_LOGIN_TEXT_MARKERS = (
    "sign in",
    "join linkedin",
    "join now",
    "email or phone",
    "password",
    "security verification",
    "let's do a quick security check",
    "verify your identity",
)
AUTH_REQUIRED_MESSAGE = (
    "LinkedIn login is required. Log in in the opened Chromium window, "
    "then start capture again. JOLT kept the browser session open."
)

_PLAYWRIGHT: Playwright | None = None
_BROWSER_CONTEXT: BrowserContext | None = None
_BROWSER_LOCK = Lock()


class ProfessionalCaptureAuthenticationRequired(RuntimeError):
    """Raised when LinkedIn blocks capture behind login/checkpoint/authwall."""


def _browser_profile_dir() -> Path:
    root = Path.cwd() / "backend" / "data" / "playwright" / "professional-capture"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _stop_browser_context() -> None:
    global _PLAYWRIGHT, _BROWSER_CONTEXT
    if _BROWSER_CONTEXT is not None:
        with suppress(Exception):
            _BROWSER_CONTEXT.close()
    _BROWSER_CONTEXT = None
    if _PLAYWRIGHT is not None:
        with suppress(Exception):
            _PLAYWRIGHT.stop()
    _PLAYWRIGHT = None


atexit.register(_stop_browser_context)


def _get_browser_context() -> BrowserContext:
    """Return one visible persistent Chromium context for Professional Capture."""
    global _PLAYWRIGHT, _BROWSER_CONTEXT
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


def _page_needs_linkedin_login(url: str, visible_text: str) -> bool:
    lowered_url = url.casefold()
    if "linkedin.com" in lowered_url and any(
        marker in lowered_url for marker in _LOGIN_URL_MARKERS
    ):
        return True
    lowered_text = visible_text.casefold()
    return any(marker in lowered_text for marker in _LOGIN_TEXT_MARKERS)


class BoundedVisibleCaptureSession:
    def __init__(
        self,
        session: Session,
        run_id: str,
        options: ProfessionalCaptureOptions,
    ) -> None:
        self.session = session
        self.run_id = run_id
        self.options = options
        self.context: BrowserContext | None = None
        self.browser_failed = False
        self.auth_required = False
        self.failure_detail = ""

    def __enter__(self) -> BoundedVisibleCaptureSession:
        with _BROWSER_LOCK:
            self.context = _get_browser_context()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def _request_stop_after_failure(self, detail: str, *, auth_required: bool = False) -> None:
        self.browser_failed = True
        self.auth_required = auth_required
        self.failure_detail = detail
        if not self.options.stop_on_failure:
            return
        run = self.session.get(ProfessionalCaptureRun, self.run_id)
        if run is not None:
            run.cancel_requested = True

    def _bounded_items(self, page: Page) -> tuple[int, str | None]:
        for selector in _ITEM_SELECTORS:
            locator = page.locator(selector)
            count = locator.count()
            if count == 0:
                continue
            maximum = self.options.max_items_per_source
            if count > maximum:
                page.evaluate(
                    """([selector, maximum]) => {
                        const items = Array.from(document.querySelectorAll(selector));
                        for (const item of items.slice(maximum)) {
                            item.setAttribute('data-jolt-capture-excluded', 'true');
                            item.style.display = 'none';
                        }
                    }""",
                    [selector, maximum],
                )
            return min(count, maximum), selector
        return 0, None

    def __call__(self, url: str) -> CapturedProfessionalPage:
        if self.browser_failed:
            raise RuntimeError(
                "The capture browser already failed; JOLT will not relaunch it in this run."
            )
        if self.context is None:
            raise RuntimeError("The bounded capture browser context is not available.")

        page: Page | None = None
        final_url = url
        page_title = ""
        try:
            page = self.context.new_page()
            with suppress(Exception):
                page.bring_to_front()
            timeout_ms = self.options.timeout_seconds * 1_000
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            final_url = page.url
            page_title = page.title()
            network_idle = True
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5_000))
            except Exception:
                network_idle = False

            visible_text = page.locator("body").inner_text(timeout=timeout_ms)
            final_url = page.url
            page_title = page.title()
            if _page_needs_linkedin_login(page.url, visible_text):
                self._request_stop_after_failure(AUTH_REQUIRED_MESSAGE, auth_required=True)
                raise ProfessionalCaptureAuthenticationRequired(AUTH_REQUIRED_MESSAGE)

            detected_items = 0
            item_selector: str | None = None
            for _ in range(self.options.max_scroll_batches):
                detected_items, item_selector = self._bounded_items(page)
                if detected_items >= self.options.max_items_per_source:
                    break
                before_height = page.evaluate("document.body.scrollHeight")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(500)
                after_height = page.evaluate("document.body.scrollHeight")
                if after_height == before_height:
                    break

            detected_items, item_selector = self._bounded_items(page)
            visible_text = page.locator("body").inner_text(timeout=timeout_ms)
            final_url = page.url
            page_title = page.title()
            if _page_needs_linkedin_login(page.url, visible_text):
                self._request_stop_after_failure(AUTH_REQUIRED_MESSAGE, auth_required=True)
                raise ProfessionalCaptureAuthenticationRequired(AUTH_REQUIRED_MESSAGE)

            body_ready = len(visible_text.strip()) >= 100
            if network_idle and body_ready:
                readiness_status = "network_idle_and_body_ready"
            elif body_ready:
                readiness_status = "body_ready"
            else:
                readiness_status = "readiness_timeout"

            item_detail = (
                f" Detected {detected_items} bounded items using {item_selector}."
                if item_selector
                else " No repeated result-card selector was detected."
            )
            readiness_detail = (
                f"Requested URL: {url}. Final URL: {final_url}. Title: {page_title}. "
                f"Visible text length: {len(visible_text.strip())}. "
                f"Applied {self.options.max_scroll_batches} maximum scroll batches, "
                f"{self.options.max_items_per_source} maximum items, and a "
                f"{self.options.timeout_seconds}-second timeout. "
                f"Using persistent browser profile {_browser_profile_dir()}.{item_detail}"
            )
            return CapturedProfessionalPage(
                screenshot_png=page.screenshot(full_page=True),
                visible_text=visible_text,
                title=page_title,
                final_url=final_url,
                http_status=response.status if response is not None else None,
                readiness_status=readiness_status,
                readiness_detail=readiness_detail,
            )
        except ProfessionalCaptureAuthenticationRequired:
            raise
        except Exception as exc:
            detail = (
                f"Requested URL: {url}. Last final URL: {final_url}. Last title: {page_title}. "
                f"Browser capture error: {type(exc).__name__}: {exc}"
            )
            self._request_stop_after_failure(detail)
            # Keep the persistent Chromium context open even after capture errors.
            # The user-present session is part of the workflow and must remain
            # available for inspection, login/checkpoint completion, and retry.
            raise RuntimeError(detail) from exc


def start_bounded_professional_capture(
    session: Session,
    run_id: str,
) -> ProfessionalCaptureRunResponse:
    run = session.get(ProfessionalCaptureRun, run_id)
    if run is None:
        raise LookupError(f"Professional capture run {run_id} was not found.")
    options = ProfessionalCaptureOptions.model_validate_json(run.capture_options_json)

    with BoundedVisibleCaptureSession(session, run_id, options) as capture_session:
        response = start_professional_supervised_capture(
            session,
            run_id,
            capture_source=capture_session,
        )

    if capture_session.browser_failed and options.stop_on_failure:
        run = session.get(ProfessionalCaptureRun, run_id)
        if run is not None:
            if capture_session.auth_required:
                run.status = "failed"
                run.stop_reason = "linkedin_login_required"
                run.cancel_requested = False
                run.current_source_id = ""
                session.commit()
                response = get_professional_capture_run(session, run_id)
            elif run.status == "cancelled":
                run.status = "failed"
                run.stop_reason = "stopped_after_first_source_failure"
                session.commit()
                response = get_professional_capture_run(session, run_id)
    return response