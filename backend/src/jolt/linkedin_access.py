from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

AUTH_PATH_MARKERS = (
    "/login",
    "/uas/login",
    "/authwall",
)
CHECKPOINT_URL_MARKERS = (
    "/checkpoint",
    "/challenge/",
)
AUTH_BODY_MARKERS = (
    "sign in",
    "join linkedin",
    "join now",
    "email or phone",
    "password",
)
CHECKPOINT_BODY_MARKERS = (
    "security verification",
    "let's do a quick security check",
    "verify your identity",
)
SAFETY_BODY_MARKERS = (
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


def detect_linkedin_access_problem(page: Any) -> tuple[str, str] | None:
    current_url = str(getattr(page, "url", "")).lower()
    parsed_url = urlparse(current_url)
    current_path = parsed_url.path
    if any(marker in current_path for marker in CHECKPOINT_URL_MARKERS):
        return "checkpoint", "LinkedIn presented a checkpoint or challenge."
    if any(marker in current_path for marker in AUTH_PATH_MARKERS):
        return "authentication_required", "LinkedIn authentication is required."

    body_text = ""
    last_error: Exception | None = None
    for _attempt in range(3):
        try:
            body_text = page.locator("body").inner_text(timeout=3_000).lower()
            last_error = None
            break
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise RuntimeError(
            "Unable to inspect LinkedIn access state after 3 attempts."
        ) from last_error

    if any(marker in body_text for marker in CHECKPOINT_BODY_MARKERS):
        return "checkpoint", "LinkedIn presented a security verification checkpoint."
    for marker in SAFETY_BODY_MARKERS:
        if marker in body_text:
            return "safety_warning", f"LinkedIn safety warning detected: {marker}."
    auth_marker_count = sum(marker in body_text for marker in AUTH_BODY_MARKERS)
    has_login_form_evidence = "email or phone" in body_text and "password" in body_text
    has_authwall_evidence = "sign in" in body_text and (
        "join linkedin" in body_text or "join now" in body_text
    )
    if has_login_form_evidence or has_authwall_evidence or auth_marker_count >= 3:
        return "authentication_required", "LinkedIn authentication is required."
    return None


def classify_navigation_exception(error: BaseException) -> str:
    message = str(error).casefold()
    network_markers = (
        "net::err_",
        "name_not_resolved",
        "internet_disconnected",
        "connection_refused",
        "connection_reset",
        "timed out",
        "timeout",
    )
    if any(marker in message for marker in network_markers):
        return "network_failure"
    return "navigation_failure"
