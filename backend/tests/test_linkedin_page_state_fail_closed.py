import pytest

from jolt.linkedin_playwright_capture import (
    _linkedin_safety_warning,
    _page_needs_linkedin_login,
)


class FailingLocator:
    def inner_text(self, *, timeout: int) -> str:
        raise TimeoutError("body inspection failed")


class FailingPage:
    url = "https://www.linkedin.com/feed/"

    def locator(self, selector: str) -> FailingLocator:
        assert selector == "body"
        return FailingLocator()


def test_login_detection_fails_closed_when_body_cannot_be_inspected() -> None:
    with pytest.raises(
        RuntimeError,
        match="Unable to inspect LinkedIn login/checkpoint state",
    ):
        _page_needs_linkedin_login(FailingPage())


def test_safety_detection_fails_closed_when_body_cannot_be_inspected() -> None:
    with pytest.raises(
        RuntimeError,
        match="Unable to inspect LinkedIn page safety state",
    ):
        _linkedin_safety_warning(FailingPage())
