"""Cross-source duplicate decisions preserve ambiguous vacancies."""

from jolt.sources.duplicate_assessment import assess_duplicate
from jolt.sources.normalized_offer import NormalizedJobOffer, Portal

DESCRIPTION = (
    "Support enterprise cloud applications and troubleshoot customer incidents. "
    "Investigate logs, coordinate with engineering and document resolutions. "
) * 3


def offer(
    portal: Portal,
    identifier: str,
    *,
    company: str = "Example Technologies",
    title: str = "Application Support Engineer",
    location: str = "Madrid",
    description: str = DESCRIPTION,
    verified: bool = True,
) -> NormalizedJobOffer:
    host = {
        "linkedin": "www.linkedin.com",
        "indeed": "es.indeed.com",
        "infojobs": "www.infojobs.net",
        "jobgether": "jobgether.com",
    }[portal]
    return NormalizedJobOffer(
        portal=portal,
        source_job_id=identifier,
        source_url=f"https://{host}/jobs/{identifier}",
        title=title,
        company=company,
        location=location,
        description=description,
        identity_verified=verified,
        detail_verified=verified,
    )


def test_same_portal_id_is_durable_duplicate() -> None:
    assert assess_duplicate(offer("linkedin", "123"), offer("linkedin", "123")).decision == (
        "same_source_offer"
    )


def test_verified_matching_offers_across_portals_are_probable_not_merged() -> None:
    first = offer("linkedin", "123")
    second = offer("infojobs", "other")
    result = assess_duplicate(first, second)
    assert result.decision == "probable_same_vacancy"
    assert first.portal == "linkedin"
    assert second.portal == "infojobs"


def test_same_job_title_different_employer_needs_review() -> None:
    result = assess_duplicate(
        offer("linkedin", "123"),
        offer("indeed", "456", company="Staffing Agency"),
    )
    assert result.decision == "needs_review"


def test_same_company_title_different_locations_needs_review() -> None:
    result = assess_duplicate(
        offer("linkedin", "123"),
        offer("infojobs", "456", location="Barcelona"),
    )
    assert result.decision == "needs_review"


def test_missing_location_or_unverified_details_needs_review() -> None:
    assert assess_duplicate(
        offer("linkedin", "123"), offer("indeed", "456", location="")
    ).decision == "needs_review"
    assert assess_duplicate(
        offer("linkedin", "123"), offer("indeed", "456", verified=False)
    ).decision == "needs_review"


def test_different_descriptions_are_distinct() -> None:
    result = assess_duplicate(
        offer("linkedin", "123"),
        offer(
            "jobgether",
            "456",
            description="Maintain factory PLC control systems and assembly robots. " * 5,
        ),
    )
    assert result.decision == "distinct"


def test_different_titles_are_distinct() -> None:
    assert assess_duplicate(
        offer("linkedin", "123"),
        offer("indeed", "456", title="Product Manager"),
    ).decision == "distinct"
