from __future__ import annotations

from jolt.jobgether_detail_fetch import extract_jobgether_detail


IDENTIFIER = "6ac5d9628a27695aea363d32"
URL = f"https://jobgether.com/offer/{IDENTIFIER}-support-technician"


def test_extracts_one_structured_official_offer_without_promoting() -> None:
    data_json = ('{"@context":"https://schema.org","@type":"JobPosting",'
        '"title":"2nd and 3rd Level IT Support Technician",'
        '"hiringOrganization":{"name":"Drees & Sommer"},'
        '"description":"Provide advanced service desk and infrastructure support to internal users across international teams, while resolving complex endpoint and network issues."}'
    )
    html = '<script type="application/ld+json">' + data_json + "</script>"
    result = extract_jobgether_detail(html, observed_id=IDENTIFIER, observed_url=URL)
    assert result["status"] == "structured_detail_present"
    assert result["company"] == "Drees & Sommer"
    assert result["validation"]["identity_consistent"] is True
    assert result["source_evidence_verified"] is False
    assert result["work_from_spain_verified"] is False


def test_missing_or_ambiguous_structured_data_remains_unresolved() -> None:
    assert extract_jobgether_detail("<html>Job description</html>", observed_id=IDENTIFIER, observed_url=URL)["status"] == "unresolved"
    html = ('<script type="application/ld+json">'
        '[{"@type":"JobPosting"},{"@type":"JobPosting"}]'
        '</script>'
    )
    assert extract_jobgether_detail(html, observed_id=IDENTIFIER, observed_url=URL)["status"] == "unresolved"


def test_rejects_observed_identity_mismatch() -> None:
    try:
        extract_jobgether_detail("", observed_id="6ac85207480485773199660a", observed_url=URL)
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("Expected mismatched source identity to be rejected")
