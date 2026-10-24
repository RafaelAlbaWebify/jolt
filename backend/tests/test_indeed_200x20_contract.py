"""Indeed 200-job / 20-page contract regression at the request boundary."""
from jolt.schemas import IndeedLiveCaptureRequest, LinkedInLiveCaptureRequest


def test_indeed_accepts_161_items_across_20_pages():
    items = [
        {"source_job_id": f"verified-{n}", "source_url": f"https://es.indeed.com/viewjob?jk=verified-{n}",
         "title": f"Support {n}", "company": "Test", "location": "Spain",
         "description": "Verified description", "identity_verified": True}
        for n in range(161)
    ]
    pages = [{"page_number": n, "visible_job_ids": []} for n in range(1, 21)]
    validated = IndeedLiveCaptureRequest.model_validate({
        "search_url": "https://es.indeed.com/jobs?q=it",
        "items": items, "pages": pages, "requested_item_limit": 200,
    })
    assert len(validated.items) == 161
    assert len(validated.pages) == 20


def test_indeed_rejects_201_items():
    from pydantic import ValidationError
    import pytest
    items = [
        {"source_job_id": str(i), "identity_verified": True, "description": "verified"}
        for i in range(201)
    ]
    with pytest.raises(ValidationError):
        IndeedLiveCaptureRequest.model_validate({"items": items})


def test_linkedin_remains_bounded_at_100_and_10():
    assert LinkedInLiveCaptureRequest.model_fields["items"].metadata[1].max_length == 100
    assert LinkedInLiveCaptureRequest.model_fields["pages"].metadata[0].max_length == 10
