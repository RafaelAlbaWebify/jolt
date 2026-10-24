"""Indeed 200-job / 20-page contract regression at the request boundary."""

from jolt.schemas import IndeedLiveCaptureRequest, LinkedInLiveCaptureRequest


def test_indeed_accepts_161_items_across_20_pages():
    items = [
        {
            "source_job_id": f"verified-{n}",
            "source_url": f"https://es.indeed.com/viewjob?jk=verified-{n}",
            "title": f"Support {n}",
            "company": "Test",
            "location": "Spain",
            "description": "Verified description",
            "identity_verified": True,
        }
        for n in range(161)
    ]
    pages = [
        {
            "page_number": n,
            "visible_job_ids": [f"verified-{i}" for i in range((n - 1) * 9, min(n * 9, 161))],
        }
        for n in range(1, 21)
    ]
    validated = IndeedLiveCaptureRequest.model_validate(
        {
            "search_url": "https://es.indeed.com/jobs?q=it",
            "items": items,
            "pages": pages,
            "requested_item_limit": 200,
        }
    )
    assert len(validated.items) == 161
    assert len(validated.pages) == 20


def test_indeed_rejects_201_items():
    import pytest
    from pydantic import ValidationError

    items = [
        {"source_job_id": str(i), "identity_verified": True, "description": "verified"}
        for i in range(201)
    ]
    with pytest.raises(ValidationError):
        IndeedLiveCaptureRequest.model_validate({"items": items})


def test_linkedin_remains_bounded_at_100_and_10():
    assert LinkedInLiveCaptureRequest.model_json_schema()["properties"]["items"]["maxItems"] == 100
    assert LinkedInLiveCaptureRequest.model_json_schema()["properties"]["pages"]["maxItems"] == 10
