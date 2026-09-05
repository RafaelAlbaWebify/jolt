from __future__ import annotations

import atexit
import json
import os
import re
import uuid
from contextlib import suppress
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from jolt.database import utc_now
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
    connection_limit: int = Field(default=100, ge=1, le=250)


class LinkedInPlaywrightBatchCaptureRequest(BaseModel):
    targets: list[LinkedInPlaywrightCaptureRequest] = Field(default_factory=list, max_length=25)


class LinkedInPlaywrightBatchCaptureResponse(BaseModel):
    captured_count: int
    captures: list[LinkedInCaptureResponse]


class LinkedInLoginRequired(RuntimeError):
    """Raised when LinkedIn asks the visible browser to authenticate."""


LOGIN_REQUIRED_MESSAGE = (
    "LinkedIn login required. Log in in the opened Chromium window, "
    "then click Capture enabled again. JOLT kept the browser session open."
)

_CONNECTIONS_PATH = "/mynetwork/invite-connect/connections"
_CONNECTION_SCHEMA = "jolt_linkedin_connections_v1"
_MAX_CONNECTION_SCROLLS = 50
_MAX_STAGNANT_SCROLLS = 3
_SCROLL_WAIT_MILLISECONDS = 1_200
_MAX_CAPTURE_TEXT_CHARACTERS = 199_000


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


def _is_connections_url(url: str) -> bool:
    return _CONNECTIONS_PATH in url.lower()


def _canonical_profile_url(url: str) -> str:
    candidate = url.strip()
    if not candidate:
        return ""
    parts = urlsplit(candidate)
    path = parts.path.rstrip("/") + "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def _normalize_connection_record(raw: object, capture_order: int) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None

    name = str(raw.get("name", "")).strip()
    profile_url = _canonical_profile_url(str(raw.get("profile_url", "")))
    headline = str(raw.get("headline", "")).strip()[:500]
    connection_context = str(raw.get("connection_context", "")).strip()[:500]

    if not name:
        return None
    if profile_url and "/in/" not in profile_url.lower():
        return None

    return {
        "name": name[:200],
        "profile_url": profile_url,
        "headline": headline,
        "connection_context": connection_context,
        "capture_order": capture_order,
    }


def _visible_connection_cards(page: Any, connection_limit: int) -> list[dict[str, object]]:
    raw_records = page.evaluate(
        """
        (limit) => {
          const ignored = new Set([
            "Message", "Connect", "Follow", "Pending", "Remove connection",
            "Send message", "More", "Show more"
          ]);
          const anchors = Array.from(document.querySelectorAll('a[href*="/in/"]'));
          const records = [];
          const seenProfiles = new Set();

          for (const anchor of anchors) {
            const href = anchor.href || anchor.getAttribute("href") || "";
            if (!href.includes("/in/")) continue;

            let profileKey = href.toLowerCase();
            try {
              const parsed = new URL(href, window.location.href);
              profileKey =
                `${parsed.origin}${parsed.pathname.replace(new RegExp("/+$"), "")}/`
                  .toLowerCase();
            } catch {
              // Keep the href fallback for malformed but visible links.
            }

            if (seenProfiles.has(profileKey)) continue;
            seenProfiles.add(profileKey);

            const card =
              anchor.closest("li") ||
              anchor.closest('[data-view-name*="connection"]') ||
              anchor.closest("article") ||
              anchor.parentElement?.parentElement ||
              anchor.parentElement;

            const rawText = card?.innerText || anchor.innerText || "";
            const lines = rawText
              .split("\\n")
              .map((line) => line.trim())
              .filter((line) => line && !ignored.has(line));

            const anchorText = (anchor.innerText || "").trim();
            const name = anchorText || lines[0] || "";
            const detailLines = lines.filter((line) => line !== name);

            const connectionContext = detailLines
              .filter((line) =>
                /\b(1st|2nd|3rd|degree|connection|connections|mutual)\b/i.test(line)
              )
              .slice(0, 3)
              .join(" · ");

            const headline = detailLines
              .filter((line) =>
                !/\b(1st|2nd|3rd|degree|connection|connections|mutual)\b/i.test(line)
              )
              .slice(0, 3)
              .join(" · ");

            if (name) {
              records.push({
                name,
                profile_url: href,
                headline,
                connection_context: connectionContext,
              });
            }

            if (records.length >= limit) break;
          }

          return records;
        }
        """,
        connection_limit,
    )
    if not isinstance(raw_records, list):
        return []

    normalized: list[dict[str, object]] = []
    for raw in raw_records:
        record = _normalize_connection_record(raw, len(normalized) + 1)
        if record is not None:
            normalized.append(record)
    return normalized


def _advance_connections_view(page: Any) -> dict[str, object]:
    """Advance the visible Connections list without assuming the page window owns scrolling.

    LinkedIn commonly renders the Connections list inside a scrollable/virtualized container.
    Scrolling only ``window`` can therefore keep returning the same visible cards forever.  Prefer
    the closest scrollable ancestor of the last visible profile anchor, then fall back to the page.
    """

    result = page.evaluate(
        """
        () => {
          const anchors = Array.from(document.querySelectorAll('a[href*="/in/"]'))
            .filter((anchor) => {
              const rect = anchor.getBoundingClientRect();
              return rect.width > 0 && rect.height > 0;
            });

          const last = anchors.length ? anchors[anchors.length - 1] : null;
          const isScrollable = (element) => {
            if (!(element instanceof HTMLElement)) return false;
            const style = window.getComputedStyle(element);
            const overflowY = style.overflowY;
            return (
              (overflowY === "auto" || overflowY === "scroll") &&
              element.scrollHeight > element.clientHeight + 2
            );
          };

          let container = last?.parentElement || null;
          while (container && container !== document.body && !isScrollable(container)) {
            container = container.parentElement;
          }

          if (container && container !== document.body && isScrollable(container)) {
            const before = container.scrollTop;
            const step = Math.max(Math.floor(container.clientHeight * 0.8), 400);
            container.scrollBy({ top: step, behavior: "instant" });
            last?.scrollIntoView({ block: "end", inline: "nearest", behavior: "instant" });
            return {
              strategy: "scrollable_container",
              before,
              after: container.scrollTop,
              scroll_height: container.scrollHeight,
              client_height: container.clientHeight,
            };
          }

          const before = window.scrollY;
          last?.scrollIntoView({ block: "end", inline: "nearest", behavior: "instant" });
          window.scrollBy({ top: Math.max(Math.floor(window.innerHeight * 0.8), 500), behavior: "instant" });
          return {
            strategy: "window",
            before,
            after: window.scrollY,
            scroll_height: document.documentElement.scrollHeight,
            client_height: window.innerHeight,
          };
        }
        """
    )
    return result if isinstance(result, dict) else {"strategy": "unknown"}


def _linkedin_safety_warning(page: Any) -> str | None:
    current_url = str(getattr(page, "url", "")).lower()
    if any(marker in current_url for marker in ("/checkpoint/challenge", "/challenge/")):
        return "LinkedIn presented a checkpoint or challenge while Connections capture was running."

    try:
        body_text = page.locator("body").inner_text(timeout=3_000).lower()
    except Exception as exc:
        raise RuntimeError("Unable to inspect LinkedIn page safety state.") from exc

    markers = (
        "your account has been temporarily restricted",
        "account has been restricted",
        "we've restricted your account",
        "we detected unusual activity",
        "we've detected unusual activity",
        "we detected automated activity",
        "we've detected automated activity",
        "too many requests",
        "rate limit",
    )
    for marker in markers:
        if marker in body_text:
            return f"LinkedIn safety warning detected: {marker}."
    return None


def _collect_connections(page: Any, connection_limit: int) -> dict[str, object]:
    records_by_identity: dict[str, dict[str, object]] = {}
    duplicate_count = 0
    observed_count = 0
    stagnant_scrolls = 0
    scroll_count = 0
    stop_reason = "maximum_scrolls_reached"
    failures: list[str] = []
    scroll_strategies: list[str] = []
    run_started_at = utc_now().isoformat()

    while scroll_count <= _MAX_CONNECTION_SCROLLS:
        if _page_needs_linkedin_login(page):
            stop_reason = "linkedin_login_or_checkpoint"
            failures.append(LOGIN_REQUIRED_MESSAGE)
            break

        safety_warning = _linkedin_safety_warning(page)
        if safety_warning is not None:
            stop_reason = "linkedin_safety_warning"
            failures.append(safety_warning)
            break

        visible_records = _visible_connection_cards(page, connection_limit)
        observed_count += len(visible_records)
        previous_unique_count = len(records_by_identity)

        for record in visible_records:
            profile_url = str(record["profile_url"])
            fallback = f"{record['name']}|{record['headline']}".casefold()
            identity = profile_url.casefold() if profile_url else fallback

            if identity in records_by_identity:
                duplicate_count += 1
                continue

            record["capture_order"] = len(records_by_identity) + 1
            record["captured_at"] = utc_now().isoformat()
            record["source_url"] = str(getattr(page, "url", ""))
            records_by_identity[identity] = record

            if len(records_by_identity) >= connection_limit:
                stop_reason = "requested_limit_reached"
                break

        if len(records_by_identity) >= connection_limit:
            break

        if len(records_by_identity) == previous_unique_count:
            stagnant_scrolls += 1
        else:
            stagnant_scrolls = 0

        if stagnant_scrolls >= _MAX_STAGNANT_SCROLLS:
            stop_reason = "no_new_connections_after_scroll"
            break

        advance = _advance_connections_view(page)
        scroll_strategies.append(str(advance.get("strategy", "unknown")))
        page.wait_for_timeout(_SCROLL_WAIT_MILLISECONDS)
        scroll_count += 1

    connections = list(records_by_identity.values())
    status = "complete" if stop_reason == "requested_limit_reached" else "partial"

    return {
        "schema": _CONNECTION_SCHEMA,
        "capture_run": {
            "requested_limit": connection_limit,
            "observed_count": observed_count,
            "unique_count": len(connections),
            "duplicate_count": duplicate_count,
            "scroll_count": scroll_count,
            "scroll_strategies": scroll_strategies,
            "stop_reason": stop_reason,
            "status": status,
            "started_at": run_started_at,
            "completed_at": utc_now().isoformat(),
            "failures": failures,
        },
        "connections": connections,
    }


def _serialize_connections_payload(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    connections = payload.get("connections")
    capture_run = payload.get("capture_run")

    if not isinstance(connections, list) or not isinstance(capture_run, dict):
        return serialized

    trimmed = False
    while len(serialized) > _MAX_CAPTURE_TEXT_CHARACTERS and connections:
        connections.pop()
        trimmed = True
        capture_run["unique_count"] = len(connections)
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    if trimmed:
        capture_run["status"] = "partial"
        capture_run["stop_reason"] = "capture_payload_limit_reached"

        failures = capture_run.get("failures")
        if not isinstance(failures, list):
            failures = []
            capture_run["failures"] = failures

        failures.append(
            "Structured Connections evidence was truncated to fit JOLT's retained capture size limit."
        )
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        while len(serialized) > _MAX_CAPTURE_TEXT_CHARACTERS and connections:
            connections.pop()
            capture_run["unique_count"] = len(connections)
            serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    return serialized


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
    global _PLAYWRIGHT, _BROWSER_CONTEXT
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
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
    current_url = page.url.lower()
    if any(
        marker in current_url
        for marker in ("/login", "/checkpoint", "/uas/login", "authwall", "session_redirect")
    ):
        return True
    try:
        body_text = page.locator("body").inner_text(timeout=3_000).lower()
    except Exception as exc:
        raise RuntimeError("Unable to inspect LinkedIn login/checkpoint state.") from exc
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
    except Exception as exc:
        raise RuntimeError(
            "Playwright is not available. Run `uv --project backend sync --dev` and install browsers."
        ) from exc

    capture_root = _capture_root()
    title = request.title.strip() or "LinkedIn capture"
    screenshot_path = capture_root / f"{_safe_slug(title)}-{uuid.uuid4().hex[:12]}.png"

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

    if _is_connections_url(final_url) or _is_connections_url(request.url):
        payload = _collect_connections(page, request.connection_limit)
        payload["source_url"] = final_url
        payload["page_title"] = page_title
        payload["raw_visible_text"] = (
            page.locator("body").inner_text(timeout=10_000).strip()[:30_000]
        )
        visible_text = _serialize_connections_payload(payload)
    else:
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
            raise RuntimeError(LOGIN_REQUIRED_MESSAGE) from exc
        except Exception:
            _reset_browser_context()
            raise
