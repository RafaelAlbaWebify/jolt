"""Regression tests for the safe two-portal search synchronizer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "tools" / "sync-definitive-job-searches.py"
SPEC = importlib.util.spec_from_file_location("search_sync", MODULE)
assert SPEC and SPEC.loader
syncmod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(syncmod)


def test_catalog_is_unique_and_bilingual():
    catalog = syncmod.desired_catalog()
    assert len(catalog["indeed"]) == 17
    assert len(catalog["linkedin"]) == 20
    assert any(
        "soporte informático" in x["url"] or "soporte+inform" in x["url"] for x in catalog["indeed"]
    )
    assert all(
        len({syncmod.search_key(x["url"]) for x in rows}) == len(rows) for rows in catalog.values()
    )


def test_semantic_key_handles_order_and_encoding():
    a = "https://www.linkedin.com/jobs/search/?keywords=application%20support&geoId=105646813&f_WT=2"
    b = "https://www.linkedin.com/jobs/search/?f_WT=2&geoId=105646813&keywords=application+support"
    assert syncmod.search_key(a) == syncmod.search_key(b)
    assert syncmod.search_key(a) != syncmod.search_key(b + "&f_TPR=r604800")


def test_reuse_existing_equivalent_ids_and_retire_extras():
    url = syncmod.desired_catalog()["linkedin"][0]["url"]
    pieces = url.split("?")
    ordered = "?".join([pieces[0], "&".join(reversed(pieces[1].split("&")))])
    old = [
        {"id": "history-1", "label": "Historic", "search_url": ordered, "enabled": False},
        {"id": "extra-2", "label": "Old experiment", "search_url": url, "enabled": False},
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
    assert sum(p[0] == "create" for p in plan) == 16


def test_backup_preserves_both_portals(tmp_path):
    state = {"indeed": [{"id": "x"}], "linkedin": [{"id": "y"}]}
    syncmod.backup(tmp_path / "backup", state, syncmod.desired_catalog())
    assert (tmp_path / "backup" / "indeed_before.json").is_file()
    assert (tmp_path / "backup" / "linkedin_before.json").is_file()
    assert (tmp_path / "backup" / "definitive_urls.csv").is_file()
