from types import SimpleNamespace

from jolt.linkedin_source_urls import absolute_linkedin_url
from jolt.opportunity_index import _display_source_url


def test_virtualized_relative_job_url_becomes_absolute() -> None:
    assert (
        absolute_linkedin_url("/jobs/view/4451234567/")
        == "https://www.linkedin.com/jobs/view/4451234567/"
    )


def test_existing_linkedin_source_document_is_normalized_on_read() -> None:
    source = SimpleNamespace(
        source_type="linkedin_live",
        source_url="/jobs/view/4451234567/?trackingId=test",
    )

    assert (
        _display_source_url(source, "")
        == "https://www.linkedin.com/jobs/view/4451234567/?trackingId=test"
    )


def test_manual_source_url_is_not_rewritten() -> None:
    source = SimpleNamespace(
        source_type="manual",
        source_url="https://example.test/job/123",
    )

    assert _display_source_url(source, "") == "https://example.test/job/123"
