from __future__ import annotations

import pytest

from jolt import infojobs_adapter
from jolt.infojobs_adapter import (
    detail_url,
    parse_detail,
    parse_listing,
    parse_search_page,
    preview_search,
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


def test_detail_rejects_stale_identity_and_empty_description() -> None:
    candidate = parse_listing(_offer("abc123"))
    valid = {
        "id": "abc123",
        "title": "Application Support Engineer",
        "description": "Handle enterprise support requests.",
        "profile": {"name": "Example Company"},
    }
    assert parse_detail(valid, candidate).description == "Handle enterprise support requests."
    with pytest.raises(ValueError, match="identity"):
        parse_detail({**valid, "id": "wrong"}, candidate)
    with pytest.raises(ValueError, match="description"):
        parse_detail({**valid, "description": " "}, candidate)
    with pytest.raises(ValueError, match="company"):
        parse_detail({**valid, "profile": {"name": "Another Company"}}, candidate)


def test_read_only_preview_pages_and_detail_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFOJOBS_CLIENT_ID", "test-client")
    monkeypatch.setenv("INFOJOBS_CLIENT_SECRET", "test-secret")
    calls: list[str] = []

    def fake_request(url: str, _client: str, _secret: str) -> object:
        calls.append(url)
        if "?q=" in url:
            if "page=1" in url:
                return {"offers": [_offer("one")], "currentPage": 1, "totalPages": 2}
            return {"offers": [_offer("one"), _offer("two")], "currentPage": 2, "totalPages": 2}
        job_id = url.rsplit("/", 1)[-1]
        return {
            "id": job_id,
            "title": "Application Support Engineer",
            "description": f"Technical support for {job_id}",
            "profile": {"name": "Example Company"},
        }

    monkeypatch.setattr(infojobs_adapter, "_request_json", fake_request)
    results = preview_search("support", page_limit=2, result_limit=3)
    assert [item.candidate.source_job_id for item in results] == ["one", "two"]
    assert len(calls) == 4


def test_preview_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INFOJOBS_CLIENT_ID", raising=False)
    monkeypatch.delenv("INFOJOBS_CLIENT_SECRET", raising=False)
    with pytest.raises(ValueError, match="INFOJOBS_CLIENT_ID"):
        preview_search("IT support")
