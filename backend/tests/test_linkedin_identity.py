from pathlib import Path

from fastapi.testclient import TestClient
from jolt.main import create_app
from jolt.url_identity import canonicalize_source_url, linkedin_job_id

FIRST_URL = (
    "https://www.linkedin.com/jobs/view/application-support-engineer-4434482145"
    "?eBP=tracking-one&refId=abc&trackingId=first"
)
SECOND_URL = (
    "https://www.linkedin.com/jobs/view/4434482145/"
    "?eBP=tracking-two&refId=xyz&trackingId=second"
)


def test_linkedin_job_identity_ignores_tracking_parameters() -> None:
    assert linkedin_job_id(FIRST_URL) == "4434482145"
    assert linkedin_job_id(SECOND_URL) == "4434482145"
    assert canonicalize_source_url(FIRST_URL) == (
        "https://www.linkedin.com/jobs/view/4434482145"
    )
    assert canonicalize_source_url(SECOND_URL) == (
        "https://www.linkedin.com/jobs/view/4434482145"
    )


def test_tracking_variants_reuse_posting_and_preserve_source_evidence(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))
    raw_text = (
        "Application Support Engineer\n"
        "Example Systems\n"
        "Location: Remote Spain\n"
        "Application support, SQL troubleshooting, incidents, and APIs."
    )

    first = client.post(
        "/api/intake/manual",
        json={"source_type": "linkedin", "source_url": FIRST_URL, "raw_text": raw_text},
    )
    second = client.post(
        "/api/intake/manual",
        json={"source_type": "linkedin", "source_url": SECOND_URL, "raw_text": raw_text},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_result = first.json()
    second_result = second.json()
    assert first_result["identity_status"] == "new"
    assert second_result["identity_status"] == "confirmed_duplicate"
    assert second_result["posting_id"] == first_result["posting_id"]
    assert second_result["evaluation_id"] == first_result["evaluation_id"]
    assert second_result["source_document_id"] != first_result["source_document_id"]
