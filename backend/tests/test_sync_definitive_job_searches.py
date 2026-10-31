"""Regression tests for the safe two-portal search synchronizer."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

MODULE = Path(__file__).resolve().parents[2] / "tools" / "sync-definitive-job-searches.py"
SPEC = importlib.util.spec_from_file_location("search_sync", MODULE)
assert SPEC and SPEC.loader
syncmod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(syncmod)


def test_catalog_has_twelve_distinct_searches_per_portal():
    catalog = syncmod.desired_catalog()
    assert len(catalog["indeed"]) == 12
    assert len(catalog["linkedin"]) == 12
    assert all(
        len({syncmod.search_key(x["url"]) for x in rows}) == len(rows) for rows in catalog.values()
    )


def test_linkedin_scope_and_remote_filters_are_explicit():
    rows = syncmod.desired_catalog()["linkedin"]
    by_label = {row["label"]: parse_qs(urlsplit(row["url"]).query) for row in rows}

    local = by_label["LinkedIn | IT | Pontevedra Local IT Support"]
    assert local["geoId"] == ["90009802"]
    assert "f_WT" not in local

    spain = by_label["LinkedIn | IT | Spain Remote IT Support"]
    assert spain["geoId"] == ["105646813"]
    assert spain["f_WT"] == ["2"]
    assert spain["f_TPR"] == ["r2592000"]

    international = {
        row["scope"]: parse_qs(urlsplit(row["url"]).query)
        for row in rows
        if row["scope"] in {"EU_REMOTE", "UK_REMOTE", "WORLD_REMOTE"}
    }
    assert international["EU_REMOTE"]["geoId"] == ["91000000"]
    assert international["UK_REMOTE"]["geoId"] == ["101165590"]
    assert international["WORLD_REMOTE"]["geoId"] == ["92000000"]
    assert all(query["f_WT"] == ["2"] for query in international.values())


def test_indeed_remote_scopes_use_their_market_sites():
    rows = syncmod.desired_catalog()["indeed"]
    by_label = {row["label"]: row["url"] for row in rows}
    local = urlsplit(by_label["Indeed | IT | Local IT Support"])
    assert local.hostname == "es.indeed.com"
    assert parse_qs(local.query)["l"] == ["Vigo, Pontevedra"]
    assert parse_qs(local.query)["radius"] == ["30"]

    remote_rows = [row for row in rows if row["scope"] != "LOCAL"]
    assert all(parse_qs(urlsplit(row["url"]).query)["l"] == ["Remote"] for row in remote_rows)
    hosts = {urlsplit(row["url"]).hostname for row in remote_rows}
    assert {
        "es.indeed.com",
        "uk.indeed.com",
        "ie.indeed.com",
        "www.indeed.com",
    } <= hosts


def test_saved_searches_use_the_certified_capture_depth():
    catalog = syncmod.desired_catalog()
    for portal, rows in catalog.items():
        payload = syncmod.payload_for(portal, rows[0])
        assert payload["max_jobs"] == 100
        if portal == "indeed":
            assert payload["definition"]["max_pages"] == 10
        else:
            assert payload["max_pages"] == 10


def test_semantic_key_handles_order_and_encoding():
    a = "https://www.linkedin.com/jobs/search/?keywords=application%20support&geoId=105646813&f_WT=2"
    b = "https://www.linkedin.com/jobs/search/?f_WT=2&geoId=105646813&keywords=application+support"
    assert syncmod.search_key(a) == syncmod.search_key(b)
    assert syncmod.search_key(a) != syncmod.search_key(b + "&f_TPR=r2592000")


def test_reuse_existing_equivalent_ids_and_retire_extras():
    url = syncmod.desired_catalog()["linkedin"][0]["url"]
    pieces = url.split("?")
    ordered = "?".join([pieces[0], "&".join(reversed(pieces[1].split("&")))])
    old = [
        {
            "id": "history-1",
            "label": "Historic",
            "search_url": ordered,
            "enabled": False,
        },
        {
            "id": "extra-2",
            "label": "Old experiment",
            "search_url": url,
            "enabled": False,
        },
    ]
    plan = syncmod.plan_portal("linkedin", old, syncmod.desired_catalog()["linkedin"])
    reuse = [x for x in plan if x[0] == "reuse"]
    assert len(reuse) == 1
    assert reuse[0][2]["id"] in {"history-1", "extra-2"}
    assert sum(x[0] == "retire" for x in plan) == 1
    payload = syncmod.payload_for("linkedin", reuse[0][1], reuse[0][2])
    assert payload["search_url"] == reuse[0][2]["search_url"]


def test_plan_does_not_mutate_records():
    catalog = syncmod.desired_catalog()
    old = {
        "id": "a",
        "label": "old",
        "enabled": True,
        "definition": {"search_url": catalog["indeed"][0]["url"]},
    }
    before = repr(old)
    plan = syncmod.plan_portal("indeed", [old], catalog["indeed"])
    assert repr(old) == before
    assert sum(p[0] == "reuse" for p in plan) == 1
    assert sum(p[0] == "create" for p in plan) == 11


def test_backup_preserves_both_portals(tmp_path):
    state = {"indeed": [{"id": "x"}], "linkedin": [{"id": "y"}]}
    syncmod.backup(tmp_path / "backup", state, syncmod.desired_catalog())
    assert (tmp_path / "backup" / "indeed_before.json").is_file()
    assert (tmp_path / "backup" / "linkedin_before.json").is_file()
    assert (tmp_path / "backup" / "definitive_urls.csv").is_file()
