from __future__ import annotations

from jolt.linkedin_access import classify_navigation_exception, detect_linkedin_access_problem


class _Body:
    def __init__(self, text: str) -> None:
        self._text = text

    def inner_text(self, timeout: int) -> str:
        assert timeout == 3000
        return self._text


class _Page:
    def __init__(self, url: str, text: str = "") -> None:
        self.url = url
        self._text = text

    def locator(self, selector: str) -> _Body:
        assert selector == "body"
        return _Body(self._text)


def test_detects_authentication_from_url() -> None:
    problem = detect_linkedin_access_problem(
        _Page("https://www.linkedin.com/login?fromSignIn=true")
    )
    assert problem is not None
    assert problem[0] == "authentication_required"


def test_detects_checkpoint_before_generic_auth() -> None:
    problem = detect_linkedin_access_problem(
        _Page("https://www.linkedin.com/checkpoint/challenge/123")
    )
    assert problem is not None
    assert problem[0] == "checkpoint"


def test_detects_authentication_and_safety_from_body() -> None:
    auth = detect_linkedin_access_problem(
        _Page("https://www.linkedin.com/jobs/search/", "Email or phone\nPassword\nSign in")
    )
    assert auth is not None
    assert auth[0] == "authentication_required"

    safety = detect_linkedin_access_problem(
        _Page(
            "https://www.linkedin.com/jobs/search/",
            "We detected unusual activity on your account.",
        )
    )
    assert safety is not None
    assert safety[0] == "safety_warning"


def test_allows_normal_jobs_page() -> None:
    assert (
        detect_linkedin_access_problem(
            _Page(
                "https://www.linkedin.com/jobs/search/?keywords=Support",
                "Jobs\nIT Support Engineer\nAbout the job",
            )
        )
        is None
    )


def test_classifies_network_navigation_failures() -> None:
    assert (
        classify_navigation_exception(RuntimeError("page.goto: net::ERR_INTERNET_DISCONNECTED"))
        == "network_failure"
    )
    assert classify_navigation_exception(TimeoutError("navigation timeout")) == "network_failure"
    assert classify_navigation_exception(RuntimeError("browser closed")) == "navigation_failure"
