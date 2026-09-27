from jolt.supervised_capture import extract_listing_metadata


def test_extract_listing_metadata_detects_promoted_and_age() -> None:
    promoted, age = extract_listing_metadata(
        "Example Co Technical Support Engineer Spain · Reposted 3 days ago "
        "Over 100 applicants Promoted by hirer"
    )
    assert promoted is True
    assert age == "Reposted 3 days ago"


def test_extract_listing_metadata_handles_plain_recent_listing() -> None:
    promoted, age = extract_listing_metadata(
        "Example Co Systems Administrator Vigo · 7 hours ago · 12 applicants"
    )
    assert promoted is False
    assert age == "7 hours ago"


def test_extract_listing_metadata_allows_missing_age() -> None:
    promoted, age = extract_listing_metadata("Example Co IT Operations Europe")
    assert promoted is False
    assert age == ""
