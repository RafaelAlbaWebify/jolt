from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

from jolt.sources.contracts import (
    CaptureRunEvidence,
    DetailEvidence,
    ListingCandidate,
    PaginationEvidence,
)


class _Node:
    def __init__(self, tag: str, attrs: dict[str, str], parent: _Node | None = None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: list[_Node] = []
        self.text_parts: list[str] = []

    @property
    def text(self) -> str:
        parts = list(self.text_parts)
        for child in self.children:
            if child.text:
                parts.append(child.text)
        return " ".join(" ".join(parts).split())

    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def find_all(self, *, tag: str | None = None, class_name: str | None = None) -> list[_Node]:
        matches: list[_Node] = []
        if (tag is None or self.tag == tag) and (
            class_name is None or class_name in self.classes()
        ):
            matches.append(self)
        for child in self.children:
            matches.extend(child.find_all(tag=tag, class_name=class_name))
        return matches

    def find_first(self, *, tag: str | None = None, class_name: str | None = None) -> _Node | None:
        matches = self.find_all(tag=tag, class_name=class_name)
        return matches[0] if matches else None


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag, {key: value or "" for key, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in {"meta", "link", "img", "input", "br", "hr"}:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.stack[-1].text_parts.append(stripped)


def _tree(html: str) -> _Node:
    parser = _TreeParser()
    parser.feed(html)
    return parser.root


def _job_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if query.get("currentJobId"):
        return query["currentJobId"][0]
    path_parts = [part for part in parsed.path.split("/") if part]
    for part in reversed(path_parts):
        if part.isdigit():
            return part
    return ""


class LinkedInFixtureAdapter:
    source_name = "linkedin"

    def parse_listing_page(self, html: str, page_number: int = 1) -> CaptureRunEvidence:
        root = _tree(html)
        listings: list[ListingCandidate] = []
        warnings: list[str] = []
        seen_ids: set[str] = set()

        for position, card in enumerate(
            root.find_all(class_name="jobs-search-results__list-item"), 1
        ):
            anchor = card.find_first(tag="a", class_name="job-card-list__title")
            if anchor is None:
                warnings.append(f"Listing position {position} has no title link.")
                continue
            source_url = anchor.attrs.get("href", "")
            source_job_id = card.attrs.get("data-job-id", "") or _job_id_from_url(source_url)
            title = anchor.text
            company_node = card.find_first(class_name="job-card-container__primary-description")
            location_node = card.find_first(class_name="job-card-container__metadata-item")
            summary_node = card.find_first(class_name="job-card-container__footer-item")

            if not source_job_id:
                warnings.append(f"Listing '{title}' has no durable job identity.")
                continue
            if source_job_id in seen_ids:
                warnings.append(f"Duplicate visible LinkedIn job ID: {source_job_id}.")
                continue
            seen_ids.add(source_job_id)
            listings.append(
                ListingCandidate(
                    source=self.source_name,
                    source_job_id=source_job_id,
                    source_url=source_url,
                    title=title,
                    company=company_node.text if company_node else "",
                    location=location_node.text if location_node else "",
                    summary=summary_node.text if summary_node else "",
                    page_number=page_number,
                    position=position,
                )
            )

        next_button = root.find_first(tag="button", class_name="artdeco-pagination__button--next")
        page = PaginationEvidence(
            page_number=page_number,
            visible_job_ids=tuple(item.source_job_id for item in listings),
            next_control_present=next_button is not None,
            next_control_enabled=bool(
                next_button is not None
                and next_button.attrs.get("disabled") is None
                and next_button.attrs.get("aria-disabled", "false").lower() != "true"
            ),
        )
        return CaptureRunEvidence(
            listings=tuple(listings),
            pages=(page,),
            warnings=tuple(warnings),
        )

    def parse_detail_page(self, html: str, expected: ListingCandidate) -> DetailEvidence:
        root = _tree(html)
        panel = root.find_first(class_name="jobs-search__job-details--container")
        if panel is None:
            return DetailEvidence(
                source=self.source_name,
                source_job_id="",
                source_url="",
                title="",
                company="",
                location="",
                description="",
                identity_verified=False,
                verification_reasons=("Detail panel was not present.",),
            )

        panel_job_id = panel.attrs.get("data-job-id", "")
        canonical = panel.find_first(tag="a", class_name="jobs-unified-top-card__job-title-link")
        source_url = canonical.attrs.get("href", "") if canonical else ""
        source_job_id = panel_job_id or _job_id_from_url(source_url)
        title_node = panel.find_first(class_name="jobs-unified-top-card__job-title") or canonical
        company_node = panel.find_first(class_name="jobs-unified-top-card__company-name")
        location_node = panel.find_first(class_name="jobs-unified-top-card__bullet")
        description_node = panel.find_first(class_name="jobs-description-content__text")
        title = title_node.text if title_node else ""
        company = company_node.text if company_node else ""

        reasons: list[str] = []
        if source_job_id != expected.source_job_id:
            reasons.append(
                f"Detail job ID {source_job_id or '<missing>'} does not match expected {expected.source_job_id}."
            )
        if title.casefold() != expected.title.casefold():
            reasons.append(
                f"Detail title '{title}' does not match listing title '{expected.title}'."
            )
        if expected.company and company.casefold() != expected.company.casefold():
            reasons.append(
                f"Detail company '{company}' does not match listing company '{expected.company}'."
            )

        return DetailEvidence(
            source=self.source_name,
            source_job_id=source_job_id,
            source_url=source_url,
            title=title,
            company=company,
            location=location_node.text if location_node else "",
            description=description_node.text if description_node else "",
            identity_verified=not reasons,
            verification_reasons=tuple(reasons),
        )
