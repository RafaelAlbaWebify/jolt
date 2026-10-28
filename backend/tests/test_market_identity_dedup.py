from datetime import UTC, datetime

from jolt.market_intelligence import (
    _deduplicate_market_postings,
    _DurableMarketPosting,
)


def _posting(
    identifier: str, url: str, title: str = "IT Support Engineer"
) -> _DurableMarketPosting:
    return _DurableMarketPosting(
        id=identifier,
        title=title,
        company="Example Ltd",
        location="Remote",
        description="The same generic job description across all listings",
        created_at=datetime.now(UTC),
        identity_key=identifier,
        canonical_url=url,
    )


def test_same_canonical_url_collapses_tracking_variants() -> None:
    first = _posting("capture-one", "https://example.com/job/1?utm_source=mail")
    second = _posting("capture-two", "https://example.com/job/1")
    unique, groups = _deduplicate_market_postings([first, second], {})
    assert len(unique) == 1
    assert len(groups) == 1
    assert groups[0]["member_posting_ids"] == ["capture-one", "capture-two"]


def test_same_title_company_and_description_with_distinct_urls_stays_distinct() -> None:
    first = _posting("requisition-one", "https://example.com/job/1")
    second = _posting("requisition-two", "https://example.com/job/2")
    unique, groups = _deduplicate_market_postings([first, second], {})
    assert len(unique) == 2
    assert groups == []


def test_missing_identifiers_never_merge_on_text_alone() -> None:
    first = _posting("", "")
    second = _posting("", "")
    first = _DurableMarketPosting(**{**first.__dict__, "id": "one"})
    second = _DurableMarketPosting(**{**second.__dict__, "id": "two"})
    unique, groups = _deduplicate_market_postings([first, second], {})
    assert len(unique) == 2
    assert groups == []
