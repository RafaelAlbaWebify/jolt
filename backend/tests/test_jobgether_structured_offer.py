import json

from jolt.jobgether_structured_offer import extract_offer


URL = "https://jobgether.com/offer/6ac5d9628a27695aea363d20-example"


def test_extract_jobposting_keeps_identifiers_separate() -> None:
    posting = {
        "@type": "JobPosting",
        "title": "Support Engineer",
        "description": "<p>First paragraph</p><ul><li>Intune support</li></ul>",
        "identifier": {"value": "6ac52363723f2bad843591c5"},
        "url": URL,
        "hiringOrganization": {"name": "Example Ltd"},
        "applicantLocationRequirements": [
            {"@type": "Country", "name": "Spain"},
            {"@type": "Country", "name": "Ireland"},
        ],
    }
    result = extract_offer(URL, [json.dumps({"@graph": [posting]})], "Support Engineer")
    assert result["status"] == "extracted_unverified"
    assert result["source_job_id"] == "6ac5d9628a27695aea363d20"
    assert result["structured_identifier"] == "6ac52363723f2bad843591c5"
    assert "Intune support" in result["description"]
    assert result["spain_declared"] is True
    assert result["work_from_spain_verified"] is False
    assert result["source_evidence_verified"] is False


def test_mismatched_structured_url_is_unresolved() -> None:
    posting = {
        "@type": "JobPosting",
        "title": "Support Engineer",
        "description": "<p>Full text</p>",
        "url": "https://jobgether.com/offer/aaaaaaaaaaaaaaaaaaaaaaaa-other",
    }
    result = extract_offer(URL, [json.dumps(posting)], "Support Engineer")
    assert result["status"] == "unresolved"
    assert result["mismatches"] == ["structured_url"]


def test_ambiguous_postings_never_promoted() -> None:
    posting = {"@type": "JobPosting", "title": "Support", "description": "Text"}
    result = extract_offer(URL, [json.dumps([posting, posting])])
    assert result["status"] == "unresolved"
    assert result["jobposting_count"] == 2


def test_bad_url_does_not_consume_json() -> None:
    result = extract_offer("https://example.com/offer/test", ["invalid"])
    assert result["status"] == "unresolved"
    assert result["reason"] == "invalid_source_url"
