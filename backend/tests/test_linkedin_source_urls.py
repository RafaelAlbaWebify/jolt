from jolt.multipage_capture import _absolute_linkedin_url


def test_normalizes_relative_linkedin_job_url() -> None:
    assert (
        _absolute_linkedin_url("/jobs/view/4443227805/?trackingId=abc")
        == "https://www.linkedin.com/jobs/view/4443227805/?trackingId=abc"
    )


def test_normalizes_protocol_relative_linkedin_job_url() -> None:
    assert (
        _absolute_linkedin_url("//www.linkedin.com/jobs/view/4443227805/")
        == "https://www.linkedin.com/jobs/view/4443227805/"
    )


def test_preserves_absolute_job_url() -> None:
    url = "https://www.linkedin.com/jobs/view/4443227805/"
    assert _absolute_linkedin_url(url) == url


def test_preserves_empty_url() -> None:
    assert _absolute_linkedin_url("") == ""
