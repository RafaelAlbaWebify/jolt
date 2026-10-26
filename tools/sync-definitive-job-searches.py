"""Safely reconcile Indeed/LinkedIn saved search portfolios via their JOLT APIs.

Read-only by default. --apply backs up both portal catalogs first, then reconciles.
Historical LinkedIn searches are disabled rather than deleted.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import Request, urlopen

# Language variants are intentionally separate when a trial found distinct roles.
# tuple: family, name, keyword, scope (L: Vigo/Pontevedra; R: Spain).
INDEED = [
    ("IT", "Application Support", 'title:"Application Support"', "R"),
    ("IT", "Technical Support Engineer", "Technical Support Engineer", "R"),
    ("IT", "IT Operations Analyst", "IT Operations Analyst", "R"),
    ("IT", "MES Support", "MES Support", "R"),
    ("IT", "IT Specialist", "IT Specialist", "L"),
    ("IT", "Service Desk", "Service Desk", "L"),
    ("IT", "IT Support", "IT Support", "L"),
    ("IT", "Manufacturing IT", "Manufacturing IT", "L"),
    ("IT", "Soporte informático", "soporte informático", "L"),
    ("Transferable", "Data Entry", "data entry", "R"),
    ("Transferable", "Customer Service", "customer service", "R"),
    ("Transferable", "Auxiliar administrativo", "auxiliar administrativo", "L"),
    ("Transferable", "Back Office", "back office", "L"),
    ("Transferable", "Atención al cliente", "atención al cliente", "L"),
    ("Transferable", "Teleoperador", "teleoperador", "L"),
    ("Transferable", "Administrativo logística", "administrativo logística", "L"),
    ("Transferable", "Recepcionista", "recepcionista", "L"),
]
LINKEDIN = [
    ("IT", "Application Support ES", "soporte de aplicaciones", "R"),
    ("IT", "Application Support EN", "application support", "R"),
    ("IT", "Technical Support EN", "technical support engineer", "R"),
    ("IT", "IT Operations EN", "IT operations", "R"),
    ("IT", "Microsoft 365 EN", "Microsoft 365 support", "R"),
    ("IT", "SaaS Support EN", "SaaS support", "R"),
    ("IT", "Soporte informático ES", "soporte informático", "L"),
    ("IT", "IT Support EN", "IT support", "L"),
    ("IT", "Técnico informático ES", "técnico informático", "L"),
    ("IT", "Informática industrial ES", "informática industrial", "L"),
    ("Transferable", "Administración ES", "auxiliar administrativo", "L"),
    ("Transferable", "Administration EN", "administrative assistant", "L"),
    ("Transferable", "Back Office EN", "back office", "L"),
    ("Transferable", "Recepción ES", "recepcionista", "L"),
    ("Transferable", "Atención al cliente ES", "atención al cliente", "L"),
    ("Transferable", "Customer Support EN", "customer support", "L"),
    ("Transferable", "Teleoperador ES", "teleoperador", "L"),
    ("Transferable", "Logística ES", "administrativo logística", "L"),
    ("Transferable", "Logistics EN", "logistics coordinator", "L"),
    ("Transferable", "Customer Support Remote EN", "customer support", "R"),
]


def search_key(url: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Compare real criteria, independent of query order and %20 versus +."""
    parsed = urlsplit(url)
    if not parsed.hostname or not parsed.path.startswith("/jobs/search"):
        if not parsed.hostname or not parsed.path.startswith("/jobs"):
            raise ValueError(f"Unexpected search URL: {url}")
    portal = "linkedin" if parsed.hostname.endswith("linkedin.com") else "indeed"
    transient = {"currentjobid", "trackingid", "refid", "origin", "refresh", "start"}
    parts = tuple(sorted(
        (key.casefold(), value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in transient
    ))
    return portal, parts


def desired_catalog() -> dict[str, list[dict]]:
    result = {"indeed": [], "linkedin": []}
    for family, name, keyword, scope in INDEED:
        location = "Vigo, Pontevedra" if scope == "L" else "España"
        params = [("q", keyword), ("l", location)]
        if scope == "L":
            params.append(("radius", "30"))
        params.append(("sort", "date"))
        url = "https://es.indeed.com/jobs?" + urlencode(params)
        result["indeed"].append({
            "label": f"Indeed | {family} | {name}", "url": url,
            "scope": scope, "keyword": keyword,
        })
    for family, name, keyword, scope in LINKEDIN:
        geo = "90009802" if scope == "L" else "105646813"
        params = [("keywords", keyword), ("geoId", geo),
                  ("f_TPR", "r604800"), ("sortBy", "DD")]
        if scope == "R":
            params.append(("f_WT", "2"))
        url = "https://www.linkedin.com/jobs/search/?" + urlencode(params)
        result["linkedin"].append({
            "label": f"LinkedIn | {family} | {name}", "url": url,
            "scope": scope, "keyword": keyword,
        })
    for portal, entries in result.items():
        keys = [search_key(x["url"]) for x in entries]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate desired {portal} criteria")
    assert len(result["indeed"]) == 17 and len(result["linkedin"]) == 20
    return result


class API:
    def __init__(self, base: str):
        if not base.startswith("http://127.0.0.1:") and not base.startswith("http://localhost:"):
            raise ValueError("Refusing nonlocal API endpoint")
        self.base = base.rstrip("/")

    def request(self, path: str, data: dict | None = None, post: bool = False):
        payload = json.dumps(data, ensure_ascii=False).encode() if data is not None else None
        req = Request(
            self.base + path, data=payload if post else None,
            method="POST" if post else "GET",
            headers={"Content-Type": "application/json"} if data is not None else {},
        )
        try:
            with urlopen(req, timeout=45) as res:
                content = res.read()
            return json.loads(content) if content else None
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Unreachable {path}: {exc.reason}") from exc

    def list(self, portal):
        endpoint = ("/api/discovery-searches?source=indeed"
                    if portal == "indeed" else "/api/linkedin-searches")
        items = self.request(endpoint)
        if not isinstance(items, list):
            raise RuntimeError(f"Unexpected {portal} response shape")
        return items


def row_url(portal, item):
    return item["definition"]["search_url"] if portal == "indeed" else item["search_url"]


def plan_portal(portal: str, current: list[dict], desired: list[dict]):
    by_key = {}
    for item in current:
        by_key.setdefault(search_key(row_url(portal, item)), []).append(item)
    operations = []
    retained = set()
    for target in desired:
        key = search_key(target["url"])
        matches = by_key.get(key, [])
        if matches:
            # Prefer exact server-stored criteria, then selected active, then stable ID.
            chosen = sorted(
                matches,
                key=lambda x: (
                    x.get("label") != target["label"],
                    not x.get("enabled", False),
                    x["id"],
                ),
            )[0]
            retained.add(chosen["id"])
            operations.append(("reuse", target, chosen))
        else:
            operations.append(("create", target, None))
    for item in current:
        if item["id"] not in retained:
            operations.append(("retire", None, item))
    return operations


def payload_for(portal, target, existing=None, *, enabled=True):
    url = row_url(portal, existing) if existing else target["url"]
    if portal == "indeed":
        return {
            "source": "indeed", "label": target["label"],
            "definition": {"search_url": url, "max_pages": 5},
            "max_jobs": 30, "enabled": enabled,
            "notes": "Definitive employability portfolio; verify eligibility and cross-portal duplicates.",
        }
    return {
        "label": target["label"], "search_url": url,
        "enabled": enabled, "max_jobs": 30, "max_pages": 5,
        "notes": "Definitive bilingual portfolio; verify Spain eligibility and cross-portal duplicates.",
    }


def assert_inactive(api):
    if api.request("/api/health").get("status") != "ok":
        raise RuntimeError("API unhealthy")
    discovery = api.request("/api/discovery-executions")
    linkedin = api.request("/api/linkedin-discovery-batches")
    active = {"queued", "scheduled", "running"}
    if any(x["source"] == "indeed" and x["status"] in active for x in discovery):
        raise RuntimeError("Active Indeed discovery; refusing mutation")
    if any(x["status"] in active for x in linkedin):
        raise RuntimeError("Active LinkedIn discovery; refusing mutation")


def backup(base_path: Path, snapshots: dict, catalog: dict):
    base_path.mkdir(parents=True, exist_ok=False)
    for portal, rows in snapshots.items():
        (base_path / f"{portal}_before.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    (base_path / "desired_urls.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    import csv as csv_lib
    import io
    buf = io.StringIO()
    writer = csv_lib.writer(buf)
    writer.writerow(["portal", "label", "keyword", "scope", "url"])
    for portal, rows in catalog.items():
        for r in rows:
            writer.writerow([portal, r["label"], r["keyword"], r["scope"], r["url"]])
    (base_path / "definitive_urls.csv").write_text(buf.getvalue(), encoding="utf-8-sig")


def sync(api: API, catalog: dict, originals: dict, *, apply: bool, output: Path):
    plans = {p: plan_portal(p, originals[p], catalog[p]) for p in catalog}
    for portal, operations in plans.items():
        counts = {name: sum(op[0] == name for op in operations)
                  for name in ("reuse", "create", "retire")}
        print(f"{portal}: {counts}")
    if not apply:
        print("DRY RUN: no API changes. To apply, use --apply.")
        return

    assert_inactive(api)
    backup(output, originals, catalog)
    print(f"BACKUP: {output}")

    # Create/reuse first; eliminate old entries only after all selected URLs exist.
    for portal in ("indeed", "linkedin"):
        for action, target, old in plans[portal]:
            if action == "retire":
                continue
            if action == "reuse":
                path = (f"/api/discovery-searches/{old['id']}" if portal == "indeed"
                        else f"/api/linkedin-searches/{old['id']}")
                # Preserve stored canonical URL: avoids LinkedIn server uniqueness clashes.
                api.request(path, payload_for(portal, target, old), post=True)
            else:
                path = ("/api/discovery-searches" if portal == "indeed"
                        else "/api/linkedin-searches")
                api.request(path, payload_for(portal, target), post=True)
            print(f"  {portal} {action}: {target['label']}")

    # Inspect again, and verify all desired URLs ACTIVE before retiring anything.
    for portal in ("indeed", "linkedin"):
        rows = api.list(portal)
        for target in catalog[portal]:
            matches = [r for r in rows if r["enabled"] and
                       search_key(row_url(portal, r)) == search_key(target["url"])]
            if not any(r["label"] == target["label"] for r in matches):
                raise RuntimeError(f"Cannot verify selected target {target['label']}")
    for portal in ("indeed", "linkedin"):
        desired_keys = {search_key(x["url"]) for x in catalog[portal]}
        rows = api.list(portal)
        # Keep exactly one active representative per semantic search.
        representatives = {}
        for target in catalog[portal]:
            matches = [r for r in rows if
                       search_key(row_url(portal, r)) == search_key(target["url"])]
            matching_label = [r for r in matches if r["label"] == target["label"]]
            chosen = (matching_label or matches)[0]
            representatives[chosen["id"]] = target
        for old in rows:
            if old["id"] in representatives:
                continue
            if portal == "indeed":
                api.request(f"/api/discovery-searches/{old['id']}/delete", post=True)
                print(f"  indeed deleted: {old['label']}")
            else:
                if old["enabled"]:
                    body = {
                        "label": old["label"], "search_url": old["search_url"],
                        "notes": old.get("notes", ""), "enabled": False,
                        "max_jobs": old["max_jobs"], "max_pages": old["max_pages"],
                    }
                    api.request(f"/api/linkedin-searches/{old['id']}", body, post=True)
                    print(f"  linkedin retired: {old['label']}")
    final = {p: api.list(p) for p in ("indeed", "linkedin")}
    for portal, expected in (("indeed", 17), ("linkedin", 20)):
        active = [x for x in final[portal] if x["enabled"]]
        keys = {search_key(row_url(portal, x)) for x in active}
        wanted = {search_key(x["url"]) for x in catalog[portal]}
        if len(active) != expected or keys != wanted:
            raise RuntimeError(f"FINAL VERIFICATION FAILED: {portal}: {len(active)} active")
    if len(final["indeed"]) != 17:
        raise RuntimeError("Indeed still contains obsolete saved searches")
    (output / "final_result.json").write_text(
        json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print("PASS: 17 Indeed + 20 LinkedIn enabled; only 17 total Indeed.")
    print("Historical LinkedIn entries are retained disabled.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--apply", action="store_true", help="Explicitly apply changes")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    api = API(args.api_url)
    assert_inactive(api)
    catalog = desired_catalog()
    originals = {p: api.list(p) for p in ("indeed", "linkedin")}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    output = args.out or Path.home() / "Downloads" / f"JOLT_SEARCH_SYNC_{stamp}"
    sync(api, catalog, originals, apply=args.apply, output=output)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
