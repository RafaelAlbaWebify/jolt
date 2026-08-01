from __future__ import annotations

import atexit
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path
from threading import Lock
from types import TracebackType

try:  # pragma: no cover - greenlet is an implementation detail of Playwright sync.
    from greenlet import getcurrent as _get_current_greenlet
except Exception:  # pragma: no cover - keep diagnostics optional.
    _get_current_greenlet = None

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
_BROWSER_OWNER_THREAD_ID: int | None = None
_BROWSER_OWNER_THREAD_NAME = ""
_BROWSER_OWNER_GREENLET_ID: int | None = None
_WORKER_EXECUTOR: ThreadPoolExecutor | None = None
_WORKER_LOCK = Lock()


class ProfessionalCaptureAuthenticationRequired(RuntimeError):
    """Raised when LinkedIn blocks capture behind login/checkpoint/authwall."""


def _truncate(value: str, limit: int = 500) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    return text if len(text) <= limit else f"{text[:limit]}…"


def _current_greenlet_id() -> int | None:
    if _get_current_greenlet is None:
        return None
    with suppress(Exception):
        return id(_get_current_greenlet())
    return None


def _runtime_diagnostics() -> str:
    current_thread = threading.current_thread()
    current_thread_id = threading.get_ident()
    current_greenlet_id = _current_greenlet_id()
    return (
        "Runtime diagnostics: "
        f"current_thread_id={current_thread_id}; "
        f"current_thread_name={current_thread.name}; "
        f"current_greenlet_id={current_greenlet_id}; "
        f"context_owner_thread_id={_BROWSER_OWNER_THREAD_ID}; "
        f"context_owner_thread_name={_BROWSER_OWNER_THREAD_NAME or 'unknown'}; "
        f"context_owner_greenlet_id={_BROWSER_OWNER_GREENLET_ID}; "
        f"context_reused={_BROWSER_CONTEXT is not None}."
    )


def _login_detection_detail(url: str, visible_text: str) -> str | None:
    lowered_url = url.casefold()
    url_markers = [
        marker
        for marker in _LOGIN_URL_MARKERS
        if "linkedin.com" in lowered_url and marker in lowered_url
    ]
    lowered_text = visible_text.casefold()
    text_markers = [marker for marker in _LOGIN_TEXT_MARKERS if marker in lowered_text]
    if not url_markers and not text_markers:
        return None
    return (
        "Login detection detail: "
        f"final_url={url}; "
        f"url_markers={url_markers}; "
        f"text_markers={text_markers}; "
        f"visible_text_length={len(visible_text.strip())}; "
        f"visible_text_excerpt={_truncate(visible_text)}."
    )


def _browser_profile_dir() -> Path:
    root = Path.cwd() / "backend" / "data" / "playwright" / "professional-capture"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _get_worker_executor() -> ThreadPoolExecutor:
    global _WORKER_EXECUTOR
    with _WORKER_LOCK:
        if _WORKER_EXECUTOR is None:
            _WORKER_EXECUTOR = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="jolt-professional-capture-playwright",
            )
        return _WORKER_EXECUTOR


def _run_on_worker(function: object, *args: object) -> object:
    executor = _get_worker_executor()
    future: Future[object] = executor.submit(function, *args)  # type: ignore[arg-type]
    return future.result()


def _stop_browser_context_on_worker() -> None:
    global _PLAYWRIGHT, _BROWSER_CONTEXT
    global _BROWSER_OWNER_THREAD_ID, _BROWSER_OWNER_THREAD_NAME, _BROWSER_OWNER_GREENLET_ID
    if _BROWSER_CONTEXT is not None:
        with suppress(Exception):
            _BROWSER_CONTEXT.close()
    _BROWSER_CONTEXT = None
    _BROWSER_OWNER_THREAD_ID = None
    _BROWSER_OWNER_THREAD_NAME = ""
    _BROWSER_OWNER_GREENLET_ID = None
    if _PLAYWRIGHT is not None:
        with suppress(Exception):
            _PLAYWRIGHT.stop()
    _PLAYWRIGHT = None


def _stop_browser_context() -> None:
    if threading.current_thread().name.startswith("jolt-professional-capture-playwright"):
        _stop_browser_context_on_worker()
        return
    with suppress(Exception):
        _run_on_worker(_stop_browser_context_on_worker)


atexit.register(_stop_browser_context)


def _get_browser_context() -> BrowserContext:
    """Return the worker-owned visible persistent Chromium context."""
    global _PLAYWRIGHT, _BROWSER_CONTEXT
    global _BROWSER_OWNER_THREAD_ID, _BROWSER_OWNER_THREAD_NAME, _BROWSER_OWNER_GREENLET_ID
    if _PLAYWRIGHT is None:
        _PLAYWRIGHT = sync_playwright().start()

    if _BROWSER_CONTEXT is not None:
        try:
            _ = _BROWSER_CONTEXT.pages
            return _BROWSER_CONTEXT
        except Exception:
            _BROWSER_CONTEXT = None
            _BROWSER_OWNER_THREAD_ID = None
            _BROWSER_OWNER_THREAD_NAME = ""
            _BROWSER_OWNER_GREENLET_ID = None

    _BROWSER_CONTEXT = _PLAYWRIGHT.chromium.launch_persistent_context(
        user_data_dir=str(_browser_profile_dir()),
        headless=False,
        no_viewport=True,
        args=["--start-maximized"],
    )
    current_thread = threading.current_thread()
    _BROWSER_OWNER_THREAD_ID = threading.get_ident()
    _BROWSER_OWNER_THREAD_NAME = current_thread.name
    _BROWSER_OWNER_GREENLET_ID = _current_greenlet_id()
    return _BROWSER_CONTEXT


def _page_needs_linkedin_login(url: str, visible_text: str) -> bool:
    return _login_detection_detail(url, visible_text) is not None


def _bounded_items(
    page: Page,
    *,
    maximum: int,
) -> tuple[int, str | None]:
    for selector in _ITEM_SELECTORS:
        locator = page.locator(selector)
        count = locator.count()
        if count == 0:
            continue
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


def _capture_with_context(
    context: BrowserContext,
    url: str,
    options: ProfessionalCaptureOptions,
) -> CapturedProfessionalPage:
    page: Page | None = None
    final_url = url
    page_title = ""
    try:
        page = context.new_page()
        with suppress(Exception):
            page.bring_to_front()
        timeout_ms = options.timeout_seconds * 1_000
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
        login_detail = _login_detection_detail(page.url, visible_text)
        if login_detail is not None:
            detail = (
                f"{AUTH_REQUIRED_MESSAGE} Page title: {page_title}. "
                f"{login_detail} {_runtime_diagnostics()}"
            )
            raise ProfessionalCaptureAuthenticationRequired(detail)

        detected_items = 0
        item_selector: str | None = None
        for _ in range(options.max_scroll_batches):
            detected_items, item_selector = _bounded_items(
                page,
                maximum=options.max_items_per_source,
            )
            if detected_items >= options.max_items_per_source:
                break
            before_height = page.evaluate("document.body.scrollHeight")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)
            after_height = page.evaluate("document.body.scrollHeight")
            if after_height == before_height:
                break

        detected_items, item_selector = _bounded_items(
            page,
            maximum=options.max_items_per_source,
        )
        visible_text = page.locator("body").inner_text(timeout=timeout_ms)
        final_url = page.url
        page_title = page.title()
        login_detail = _login_detection_detail(page.url, visible_text)
        if login_detail is not None:
            detail = (
                f"{AUTH_REQUIRED_MESSAGE} Page title: {page_title}. "
                f"{login_detail} {_runtime_diagnostics()}"
            )
            raise ProfessionalCaptureAuthenticationRequired(detail)

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
            f"Applied {options.max_scroll_batches} maximum scroll batches, "
            f"{options.max_items_per_source} maximum items, and a "
            f"{options.timeout_seconds}-second timeout. "
            f"Using persistent browser profile {_browser_profile_dir()}.{item_detail} "
            f"{_runtime_diagnostics()}"
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
            f"Browser capture error: {type(exc).__name__}: {exc}. "
            f"{_runtime_diagnostics()}"
        )
        raise RuntimeError(detail) from exc


def _capture_on_worker(
    url: str,
    options: ProfessionalCaptureOptions,
) -> CapturedProfessionalPage:
    return _capture_with_context(_get_browser_context(), url, options)


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
        # Kept as a test injection seam. Production calls leave this as None and
        # all Playwright work is submitted to the single dedicated worker.
        self.context: BrowserContext | None = None
        self.browser_failed = False
        self.auth_required = False
        self.failure_detail = ""

    def __enter__(self) -> BoundedVisibleCaptureSession:
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

    def __call__(self, url: str) -> CapturedProfessionalPage:
        if self.browser_failed:
            raise RuntimeError(
                "The capture browser already failed; JOLT will not relaunch it in this run."
            )

        try:
            if self.context is not None:
                return _capture_with_context(self.context, url, self.options)
            captured = _run_on_worker(_capture_on_worker, url, self.options)
            return captured  # type: ignore[return-value]
        except ProfessionalCaptureAuthenticationRequired as exc:
            detail = str(exc)
            self._request_stop_after_failure(detail, auth_required=True)
            raise
        except Exception as exc:
            detail = str(exc)
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
