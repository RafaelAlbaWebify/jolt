from __future__ import annotations

import pytest

from jolt.infojobs_adapter import (
    detail_url,
    parse_listing,
    parse_search_page,
    search_url,
)


def _offer(job_id: str = "abc123") -> dict[str, object]:
    return {
        "id": job_id,
        "title": "Application Support Engineer",
        "link": f"https://www.infojobs.net/oferta/{job_id}",
        "author": {"name": "Example Company"},
        "city": "Vigo",
        "province": {"value": "Pontevedra"},
    }


def test_search_url_is_bounded_and_encoded() -> None:
    url = search_url("soporte IT & sistemas", page=2, max_results=30, province="pontevedra")
    assert "q=soporte+IT+%26+sistemas" in url
    assert "page=2" in url
    assert "maxResults=30" in url
    assert "province=pontevedra" in url
    with pytest.raises(ValueError):
        search_url("support", max_results=51)
    with pytest.raises(ValueError):
        search_url("", page=1)


def test_listing_identity_and_page_provenance() -> None:
    offers, current, total = parse_search_page(
        {"offers": [_offer("a1"), _offer("a2")], "currentPage": 1, "totalPages": 3}
    )
    assert current == 1
    assert total == 3
    assert [offer.source_job_id for offer in offers] == ["a1", "a2"]
    assert offers[0].company == "Example Company"
    assert offers[0].location == "Vigo, Pontevedra"
    assert offers[0].source == "infojobs"


def test_reject_missing_evidence_and_duplicate_ids() -> None:
    invalid = _offer()
    invalid["author"] = {}
    with pytest.raises(ValueError):
        parse_listing(invalid)
    invalid = _offer()
    invalid["link"] = "https://example.com/offer"
    with pytest.raises(ValueError):
        parse_listing(invalid)
    with pytest.raises(ValueError):
        parse_search_page({"offers": [_offer(), _offer()], "currentPage": 1, "totalPages": 2})
    with pytest.raises(ValueError):
        parse_search_page({"offers": [], "currentPage": 2, "totalPages": 1})
    with pytest.raises(ValueError):
        detail_url("../untrusted")
