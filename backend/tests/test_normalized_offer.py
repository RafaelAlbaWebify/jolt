"""Common offer contract compatibility tests for current capture formats."""

import hashlib

import pytest
from pydantic import ValidationError

from jolt.sources.normalized_offer import normalize_captured_offer


@pytest.mark.parametrize(
    ("portal", "host", "identifier"),
    [
        ("linkedin", "www.linkedin.com", "123456"),
        ("indeed", "es.indeed.com", "a1b2c3"),
    ],
)
def test_existing_live_capture_fields_normalize(portal, host, identifier) -> None:
    offer = normalize_captured_offer(
        portal,
        {
            "source_job_id": identifier,
            "source_url": f"https://{host}/jobs/view/{identifier}",
            "title": "Support Engineer",
            "company": "Example",
            "location": "Madrid",
            "description": "Technical support and operations",
            "identity_verified": True,
        },
    )
    assert offer.portal == portal
    assert offer.source_job_id == identifier
    assert offer.identity_verified
    assert offer.detail_verified
    assert offer.work_mode == "unknown"
    assert offer.salary_text is None
    assert offer.work_from_spain_verified is False


def test_infojobs_complete_captured_body_normalizes() -> None:
    title = "IT Support Engineer"
    body = (
        "Buscar empleo\n" + title + "\nGuardar\nExample Employer\n"
        "Madrid (Madrid)\nRemoto\nRequisitos\nDescripción\n"
        + ("Support endpoints, cloud services and workplace systems. " * 6)
        + "\nCategoría\nInformática\nNosotros\n"
    )
    offer = normalize_captured_offer(
        "infojobs",
        {
            "url": "https://www.infojobs.net/madrid/support/of-i9a3c6c996942d0b2d0f19cacaf8f2e",
            "title_observed": title,
            "status": "extracted_unverified",
            "body_text": body,
            "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        },
    )
    assert offer.company == "Example Employer"
    assert offer.location == "Madrid (Madrid)"
    assert offer.description.startswith("Support endpoints")
    assert offer.identity_verified
    assert offer.detail_verified
    assert offer.work_from_spain_verified is False


def test_infojobs_tampered_content_rejected() -> None:
    with pytest.raises(ValueError, match="body hash mismatch"):
        normalize_captured_offer(
            "infojobs",
            {
                "url": "https://www.infojobs.net/madrid/support/of-i9a3c6c996942d0b2d0f19cacaf8f2e",
                "title_observed": "Support",
                "status": "extracted_unverified",
                "body_text": "Support\nDescripción\n" + "x" * 200 + "\nCategoría\n",
                "body_sha256": "0" * 64,
            },
        )


def test_jobgether_complete_structured_capture_normalizes() -> None:
    identifier = "a" * 24
    offer = normalize_captured_offer(
        "jobgether",
        {
            "source_job_id": identifier,
            "url": f"https://jobgether.com/offer/{identifier}-support-engineer",
            "title": "Application Support",
            "company": "Example",
            "description": "Diagnose business applications and investigate technical issues. " * 4,
            "status": "extracted_unverified",
            "mismatches": [],
            "spain_declared": True,
        },
    )
    assert offer.source_job_id == identifier
    assert offer.identity_verified
    assert offer.detail_verified
    assert offer.work_from_spain_verified is False


def test_jobgether_identity_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="identity mismatch"):
        normalize_captured_offer(
            "jobgether",
            {
                "source_job_id": "b" * 24,
                "url": f"https://jobgether.com/offer/{'a' * 24}-support",
                "title": "Support",
                "company": "Example",
            },
        )


def test_cross_portal_url_is_rejected() -> None:
    with pytest.raises(ValueError, match="does not belong"):
        normalize_captured_offer(
            "linkedin",
            {
                "source_job_id": "123",
                "source_url": "https://es.indeed.com/viewjob?jk=123",
                "title": "Support",
                "company": "Example",
            },
        )


def test_missing_company_is_not_silently_fabricated() -> None:
    with pytest.raises(ValidationError):
        normalize_captured_offer(
            "indeed",
            {
                "source_job_id": "123",
                "source_url": "https://es.indeed.com/viewjob?jk=123",
                "title": "Support",
                "company": "",
            },
        )


def test_unverified_evidence_stays_unverified() -> None:
    offer = normalize_captured_offer(
        "indeed",
        {
            "source_job_id": "123",
            "source_url": "https://es.indeed.com/viewjob?jk=123",
            "title": "Support",
            "company": "Example",
            "description": "Text",
            "identity_verified": False,
        },
    )
    assert not offer.identity_verified
    assert not offer.detail_verified
