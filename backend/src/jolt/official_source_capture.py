"""Bounded, opt-in capture of public official ATS evidence.

Network requests are never performed implicitly during AI export.
Only links already discovered in captured vacancy text and belonging to
approved ATS domains are eligible. Requests do not follow redirects.
"""
from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import PostingSourceIdentity, SourceDocument, utc_now
from jolt.external_evidence_preflight import _ATS_DOMAINS

USER_AGENT = "JOLT-EvidencePreflight/1.0"
MAX_BYTES = 350_000
MAX_ITEMS_PER_REQUEST = 10
CACHE_TTL = timedelta(days=7)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        elif tag in {"p", "li", "h1", "h2", "h3", "div", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(self.hidden - 1, 0)

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def allowed_source_url(url: str) -> bool:
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower()
    except ValueError:
        return False
    return bool(
        p.scheme == "https" and not p.username and not p.password
        and p.port in (None, 443)
        and host and any(host == site or host.endswith("." + site)
                         for site in _ATS_DOMAINS)
    )


def _open_limited(url: str, *, timeout: float = 8) -> tuple[int, bytes, str]:
    opener = urllib.request.build_opener(
        _NoRedirect, urllib.request.ProxyHandler({})
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"}
    )
    with opener.open(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
        if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
            raise ValueError("Unsupported content type")
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Source too large")
        return response.status, data, content_type


def _robots_permits(url: str) -> bool:
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        _, contents, _ = _open_robots(robots_url)
    except (OSError, ValueError, urllib.error.HTTPError):
        return False
    robot = urllib.robotparser.RobotFileParser()
    robot.parse(contents.decode("utf-8", errors="replace").splitlines())
    return robot.can_fetch(USER_AGENT, url)


def _open_robots(url: str) -> tuple[int, bytes, str]:
    opener = urllib.request.build_opener(
        _NoRedirect, urllib.request.ProxyHandler({})
    )
    with opener.open(
        urllib.request.Request(url, headers={"User-Agent": USER_AGENT}),
        timeout=6,
    ) as response:
        data = response.read(100_001)
        if len(data) > 100_000:
            raise ValueError("robots.txt too large")
        return response.status, data, "text/plain"


def _plain_text(data: bytes, content_type: str) -> str:
    decoded = data.decode("utf-8", errors="replace")
    if content_type == "text/plain":
        return " ".join(decoded.split())[:25_000]
    parser = _HTMLText()
    parser.feed(decoded)
    return " ".join("".join(parser.parts).split())[:25_000]


def _link_id(posting_id: str, url: str) -> str:
    return hashlib.sha256(f"{posting_id}|{url}".encode()).hexdigest()[:60]


def _existing_source(session: Session, posting_id: str, url: str):
    return session.scalar(
        select(PostingSourceIdentity).where(
            PostingSourceIdentity.portal == "official_ats_preflight",
            PostingSourceIdentity.source_job_id == _link_id(posting_id, url),
        )
    )


def capture_official_candidates(
    session: Session, inbox: dict[str, Any] | None, *, max_jobs: int = 10,
) -> dict[str, Any]:
    """Fetch at most max_jobs public ATS candidate pages; preserve evidence in DB."""
    if not 1 <= max_jobs <= MAX_ITEMS_PER_REQUEST:
        raise ValueError(f"max_jobs must be 1..{MAX_ITEMS_PER_REQUEST}")
    jobs = inbox.get("jobs", []) if isinstance(inbox, dict) else []
    selected: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    search_count = 0
    search_enabled = True
    search_statuses: dict[str, int] = {}
    for job in jobs:
        if not isinstance(job, dict) or not isinstance(job.get("posting_id"), str):
            continue
        suggestions = job.get("external_evidence_preflight", {}).get(
            "official_source_candidates", []
        )
        if not isinstance(suggestions, list):
            suggestions = []
        if not suggestions and search_enabled and search_count < max_jobs:
            # Provider discovery is optional, separately rate-bounded and never
            # treated as a verified match to this particular job.
            from jolt.official_ats_discovery import discover_ats_candidates
            discovery = discover_ats_candidates(
                title=str(job.get("title", "")),
                company=str(job.get("company", "")),
            )
            status = str(discovery.get("status", "unknown"))
            search_statuses[status] = search_statuses.get(status, 0) + 1
            if status == "provider_not_configured":
                # Continue processing links already present later in the batch.
                search_enabled = False
            else:
                search_count += 1
                suggestions = discovery.get("candidates", [])
        for candidate in suggestions:
            if not isinstance(candidate, dict):
                continue
            url = str(candidate.get("url", ""))
            pair = (job["posting_id"], url)
            if pair in seen or not allowed_source_url(url):
                continue
            seen.add(pair)
            selected.append(pair)
    attempted = 0
    cached = 0
    results: list[dict[str, str]] = []
    for posting_id, url in selected:
        if attempted >= max_jobs:
            break
        link = _existing_source(session, posting_id, url)
        if link is not None and link.source_document_id:
            doc = session.get(SourceDocument, link.source_document_id)
            if doc is not None and doc.captured_at.replace(tzinfo=UTC) >= datetime.now(UTC) - CACHE_TTL:
                cached += 1
                continue
        attempted += 1
        if not _robots_permits(url):
            results.append({"posting_id": posting_id, "url": url, "status": "robots_unavailable_or_disallowed"})
            continue
        try:
            status, data, content_type = _open_limited(url)
            body = _plain_text(data, content_type)
            if not body:
                results.append({"posting_id": posting_id, "url": url, "status": "empty_body"})
                continue
            now = utc_now()
            doc = SourceDocument(
                id=str(uuid4()), source_type="official_ats_preflight",
                source_url=url, raw_text=body,
                content_hash=hashlib.sha256(data).hexdigest(), captured_at=now,
            )
            session.add(doc)
            session.flush()
            if link is None:
                link = PostingSourceIdentity(
                    id=str(uuid4()), posting_id=posting_id,
                    portal="official_ats_preflight", source_job_id=_link_id(posting_id, url),
                    source_url=url, first_seen_at=now, last_seen_at=now,
                    source_document_id=doc.id,
                )
                session.add(link)
            else:
                link.source_document_id = doc.id
                link.last_seen_at = now
            results.append({"posting_id": posting_id, "url": url,
                            "status": "captured_identity_unverified", "http_status": str(status)})
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            results.append({"posting_id": posting_id, "url": url, "status": "fetch_failed",
                            "detail": type(exc).__name__})
        # Local execution must not hammer an ATS. Bounded to <=10 per request.
        time.sleep(0.5)
    session.commit()
    return {
        "candidate_links": len(selected), "attempted": attempted,
        "cached_fresh": cached, "remaining_or_skipped": max(0, len(selected) - attempted - cached),
        "provider_searches": search_count, "provider_statuses": search_statuses,
        "results": results,
    }


def attach_captured_official_sources(
    session: Session, inbox: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Add bounded persisted evidence without claiming identity or Spain eligibility."""
    if inbox is None:
        return None
    jobs = inbox.get("jobs", [])
    if not isinstance(jobs, list):
        return inbox
    by_posting: dict[str, list[dict[str, Any]]] = {}
    for link in session.scalars(
        select(PostingSourceIdentity).where(
            PostingSourceIdentity.portal == "official_ats_preflight"
        )
    ).all():
        if not link.source_document_id:
            continue
        doc = session.get(SourceDocument, link.source_document_id)
        if doc is None:
            continue
        by_posting.setdefault(link.posting_id, []).append({
            "source_url": doc.source_url,
            "captured_at": doc.captured_at.isoformat(),
            "content_hash": doc.content_hash,
            "captured_text_excerpt": doc.raw_text[:12_000],
            "capture_status": "captured_identity_unverified",
            "source_type": doc.source_type,
            "authority": "candidate_official_ats_not_verified_job_identity",
        })
    for job in jobs:
        if isinstance(job, dict):
            job.setdefault("external_evidence_preflight", {})[
                "captured_official_sources"
            ] = by_posting.get(str(job.get("posting_id", "")), [])[:5]
    inbox.setdefault("preflight_metadata", {})[
        "jobs_with_captured_official_sources"
    ] = sum(bool(job.get("external_evidence_preflight", {}).get(
        "captured_official_sources")) for job in jobs if isinstance(job, dict))
    return inbox
