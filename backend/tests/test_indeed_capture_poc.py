from __future__ import annotations

from jolt.indeed_capture import canonical_indeed_job_url, extract_indeed_job_key
from jolt.schemas import IndeedLiveCaptureRequest
from jolt.url_identity import canonicalize_source_url, indeed_job_key


def test_extracts_indeed_job_key_from_viewjob_url() -> None:
    url = "https://es.indeed.com/viewjob?jk=6679e1407fc705be&utm_source=test"
    assert extract_indeed_job_key(url) == "6679e1407fc705be"
    assert indeed_job_key(url) == "6679e1407fc705be"


def test_canonicalizes_indeed_job_url_by_job_key() -> None:
    url = "https://es.indeed.com/viewjob?jk=6679e1407fc705be&from=serp&vjk=ignored"
    assert canonical_indeed_job_url(url) == "https://es.indeed.com/viewjob?jk=6679e1407fc705be"
    assert canonicalize_source_url(url) == "https://www.indeed.com/viewjob?jk=6679e1407fc705be"


def test_indeed_capture_contract_is_bounded_to_ten_jobs() -> None:
    payload = {
        "search_url": "https://es.indeed.com/jobs?q=it+support",
        "requested_item_limit": 1,
        "items": [
            {
                "source_job_id": "abc123",
                "source_url": "https://es.indeed.com/viewjob?jk=abc123",
                "title": "IT Support",
                "company": "Example",
                "location": "Vigo",
                "description": "Support users and Windows systems.",
                "identity_verified": True,
                "verification_reason": "",
            }
        ],
    }

    request = IndeedLiveCaptureRequest.model_validate(payload)
    assert request.items[0].source_job_id == "abc123"
    assert request.requested_item_limit == 1
