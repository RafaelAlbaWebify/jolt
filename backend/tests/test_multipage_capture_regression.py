from __future__ import annotations

from jolt.multipage_capture import (
    _detail_company,
    _detail_description,
    _detail_location,
)


class FakeFirst:
    def __init__(self, text: str) -> None:
        self.text = text

    def inner_text(self, timeout: int = 0) -> str:
        del timeout
        return self.text


class FakeLocator:
    def __init__(self, text: str | None) -> None:
        self.text = text
        self.first = FakeFirst(text or "")

    def count(self) -> int:
        return 0 if self.text is None else 1


class FakePage:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.requested_selectors: list[str] = []

    def locator(self, selector: str) -> FakeLocator:
        self.requested_selectors.append(selector)
        return FakeLocator(self.values.get(selector))


def test_real_linkedin_description_container_is_preferred() -> None:
    description = (
        "About the job Role: Platform Systems Analyst (Remote) "
        "We are hiring a Computer Systems Analyst to evaluate and "
        "optimize systems and infrastructure."
    )

    page = FakePage(
        {
            "#job-details": description,
            ".jobs-search__job-details--container": (
                "Large generic container that should not be needed."
            ),
        }
    )

    assert _detail_description(page) == description
    assert page.requested_selectors[0] == "#job-details"


def test_detail_header_removes_listing_action_pollution() -> None:
    page = FakePage(
        {
            ".job-details-jobs-unified-top-card__company-name": ("Hire Feed"),
        }
    )

    assert _detail_company(page) == "Hire Feed"


def test_detail_location_discards_age_and_apply_metadata() -> None:
    page = FakePage(
        {
            ".job-details-jobs-unified-top-card__primary-description-container": (
                "European Union ? 3 hours ago ? 0 people clicked apply"
            ),
        }
    )

    assert _detail_location(page) == "European Union"


def test_description_requires_usable_text() -> None:
    page = FakePage(
        {
            "#job-details": "About the job",
        }
    )

    assert _detail_description(page) == ""
