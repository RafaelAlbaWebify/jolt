from __future__ import annotations

from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel


class ProfessionalSourceCategory(StrEnum):
    PROFILE = "profile"
    NETWORK = "network"
    CAREER = "career"


class ProfessionalIntelligenceSource(BaseModel):
    source_id: str
    label: str
    category: ProfessionalSourceCategory
    url: str
    initial_scope: bool
    capture_mode: str = "supervised_read_only"


_CONFIRMED_SOURCES = (
    ProfessionalIntelligenceSource(
        source_id="linkedin-profile",
        label="Main profile",
        category=ProfessionalSourceCategory.PROFILE,
        url="https://www.linkedin.com/in/rafael-alba-tech/",
        initial_scope=True,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-experience",
        label="Experience",
        category=ProfessionalSourceCategory.PROFILE,
        url="https://www.linkedin.com/in/rafael-alba-tech/details/experience/",
        initial_scope=True,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-featured",
        label="Featured",
        category=ProfessionalSourceCategory.PROFILE,
        url="https://www.linkedin.com/in/rafael-alba-tech/details/featured/",
        initial_scope=True,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-activity-all",
        label="All activity",
        category=ProfessionalSourceCategory.PROFILE,
        url="https://www.linkedin.com/in/rafael-alba-tech/recent-activity/all/",
        initial_scope=True,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-certifications",
        label="Certifications",
        category=ProfessionalSourceCategory.PROFILE,
        url="https://www.linkedin.com/in/rafael-alba-tech/details/certifications/",
        initial_scope=True,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-skills",
        label="Skills",
        category=ProfessionalSourceCategory.PROFILE,
        url="https://www.linkedin.com/in/rafael-alba-tech/details/skills/",
        initial_scope=True,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-connections",
        label="Connections",
        category=ProfessionalSourceCategory.NETWORK,
        url="https://www.linkedin.com/mynetwork/invite-connect/connections/",
        initial_scope=False,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-groups",
        label="Groups",
        category=ProfessionalSourceCategory.NETWORK,
        url="https://www.linkedin.com/groups/",
        initial_scope=False,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-pages",
        label="Pages",
        category=ProfessionalSourceCategory.NETWORK,
        url="https://www.linkedin.com/mynetwork/network-manager/company/",
        initial_scope=False,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-newsletters",
        label="Newsletters",
        category=ProfessionalSourceCategory.NETWORK,
        url="https://www.linkedin.com/mynetwork/network-manager/newsletters/",
        initial_scope=False,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-notifications",
        label="Notifications",
        category=ProfessionalSourceCategory.NETWORK,
        url="https://www.linkedin.com/notifications/?filter=all",
        initial_scope=False,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-feed",
        label="Feed",
        category=ProfessionalSourceCategory.NETWORK,
        url="https://www.linkedin.com/feed/",
        initial_scope=False,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-jobs-preferences",
        label="Jobs based on preferences",
        category=ProfessionalSourceCategory.CAREER,
        url="https://www.linkedin.com/jobs/search-results/?currentJobId=4442217692&keywords=Information%20Technology%20Operations%20Engineer%20or%20Information%20Technology%20Infrastructure%20Engineer%20or%20System%20Administrator%20or%20Information%20Technology%20Support%20Engineer%20or%20Technical%20Support%20Engineer%2C%20remote%20or%20hybrid&origin=PREFERENCES_LANDING&originToLandingJobPostings=4442217692%2C4444455937%2C4437920364&geoId=101165590%2C103644278%2C104524525%2C104738515",
        initial_scope=True,
    ),
    ProfessionalIntelligenceSource(
        source_id="linkedin-jobs-profile-match",
        label="Jobs that match the profile",
        category=ProfessionalSourceCategory.CAREER,
        url="https://www.linkedin.com/jobs/search-results/?currentJobId=4442012588&showHowYouFit=HOW_YOU_FIT&keywords=Freelance%20%2F%20B2B%20IT%20Support%20%26%20Digital%20Operations&origin=QUALIFICATION_LANDING&originToLandingJobPostings=4442012588%2C4424359434%2C4439124963%2C4436389124&geoId=90009818",
        initial_scope=True,
    ),
)


def _validate_registry() -> None:
    source_ids = [source.source_id for source in _CONFIRMED_SOURCES]
    urls = [source.url for source in _CONFIRMED_SOURCES]
    if len(source_ids) != len(set(source_ids)):
        raise RuntimeError("Professional Intelligence source IDs must be unique.")
    if len(urls) != len(set(urls)):
        raise RuntimeError("Professional Intelligence source URLs must be unique.")
    for source in _CONFIRMED_SOURCES:
        parsed = urlparse(source.url)
        if parsed.scheme != "https" or parsed.hostname not in {"linkedin.com", "www.linkedin.com"}:
            raise RuntimeError(f"Unsupported Professional Intelligence source URL: {source.url}")


_validate_registry()


def list_professional_intelligence_sources() -> list[ProfessionalIntelligenceSource]:
    """Return the confirmed, user-approved LinkedIn source registry.

    This registry is configuration only. It does not launch a browser, reuse a session,
    or perform any LinkedIn account action.
    """
    return [source.model_copy() for source in _CONFIRMED_SOURCES]
