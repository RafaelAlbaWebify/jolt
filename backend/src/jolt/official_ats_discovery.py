"""Optional search-provider discovery of employer ATS job-page candidates.

The provider is used only by an explicit operator-triggered refresh.
Search results are unverified leads, never proof of role identity or location.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any

from jolt.official_source_capture import allowed_source_url


def discover_ats_candidates(
    *,
    title: str,
    company: str,
    api_key: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    key = (api_key if api_key is not None else os.getenv("JOLT_BRAVE_SEARCH_API_KEY", "")).strip()
    if not key:
        return {"status": "provider_not_configured", "candidates": []}
    if not title.strip() or not company.strip():
        return {"status": "insufficient_identity", "candidates": []}
    if not 1 <= limit <= 10:
        raise ValueError("limit must be 1..10")
    query = f'"{company[:100]}" "{title[:160]}" jobs apply official ATS'
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({
        "q": query,
        "count": limit,
    })
    req = urllib.request.Request(
        url, headers={
            "Accept": "application/json",
            "X-Subscription-Token": key,
            "User-Agent": "JOLT-EvidencePreflight/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status != 200:
                return {"status": "provider_error", "candidates": []}
            data = response.read(250_001)
        if len(data) > 250_000:
            return {"status": "provider_response_too_large", "candidates": []}
        parsed = json.loads(data)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"status": "provider_unavailable", "candidates": []}
    entries = parsed.get("web", {}).get("results", [])
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        target = str(entry.get("url", ""))
        if target in seen or not allowed_source_url(target):
            continue
        seen.add(target)
        candidates.append({
            "url": target, "source": "brave_search_provider",
            "verification_status": "unverified_candidate",
            "result_title": str(entry.get("title", ""))[:240],
        })
    return {"status": "searched", "candidates": candidates}
